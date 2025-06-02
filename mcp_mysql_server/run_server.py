from typing import Any, Dict, Optional, List
import os 
import logging
from dotenv import load_dotenv
import pymysql
import pymysql.cursors
from mcp.server.fastmcp import FastMCP
import re
import time

# Load environment variables
load_dotenv()

# Create MCP server instance
mcp = FastMCP("mysql-server")

# Database connection configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "test"),
    "passwd": os.getenv("DB_PASSWORD", "test"), 
    "db": os.getenv("DB_NAME", "test_db"),  
    "port": int(os.getenv("DB_PORT", 3306))
}

# Global query log storage
query_logs = []  # List of all query logs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql-mcp-server")

def log_query(operation: str, success: bool, error: str = None):
    """
    记录查询日志（不区分客户端）
    """
    log_entry = {
        "timestamp": time.time(),
        "operation": operation,
        "success": success,
        "error_msg": error
    }
    
    # 添加到全局日志列表
    query_logs.append(log_entry)

@mcp.tool()
def get_query_logs(limit: int = 5) -> Dict[str, Any]:
    """获取查询日志
    
    Args:
        limit: 可选参数，指定返回的日志数量，默认为20
    """
    # 验证limit参数
    if limit <= 0:
        return {
            "success": False,
            "error": "Limit must be a positive integer"
        }
    
    # 获取最近的日志
    logs = query_logs[-limit:] if limit < len(query_logs) else query_logs
    
    # 转换时间戳为可读格式
    formatted_logs = []
    for log in logs:
        formatted_log = log.copy()
        formatted_log["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", 
                              time.localtime(log["timestamp"]))
        formatted_logs.append(formatted_log)
    
    return {
        "success": True,
        "logs": formatted_logs,
        "total_queries": len(query_logs)
    }

# Connect to MySQL database
def get_connection():
    try:
        return pymysql.connect(**DB_CONFIG)
    except pymysql.Error as e:
        print(f"Database connection error: {e}")
        raise


@mcp.tool()
def get_schema(table_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """获取数据库表结构信息，支持按表名过滤
    
    Args:
        table_names: 可选参数，指定要获取的表名列表。如果为None则返回所有表
    """
    conn = get_connection()
    cursor = None
    try:
        # Create dictionary cursor
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get all table names
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        all_table_names = [list(table.values())[0] for table in tables]
        
        # Filter tables if table_names is provided
        if table_names is not None:
            # 确保请求的表名都存在
            valid_tables = [name for name in table_names if name in all_table_names]
            if not valid_tables:
                return {
                    "success": False,
                    "error": "None of the specified tables exist in the database"
                }
            table_names_to_query = valid_tables
        else:
            table_names_to_query = all_table_names
        
        # Get structure for each table
        schema = {}
        for table_name in table_names_to_query:
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = cursor.fetchall()
            table_schema = []
            
            for column in columns:
                table_schema.append({
                    "name": column["Field"],
                    "type": column["Type"],
                    "null": column["Null"],
                    "key": column["Key"],
                    "default": column["Default"],
                    "extra": column["Extra"]
                })
            
            schema[table_name] = table_schema

        # 记录成功日志
        log_query(operation=f"get_schema for tables: {table_names_to_query}", success=True)

        return {
            "success": True,
            "database": DB_CONFIG["db"],
            "tables": schema
        }
    except Exception as e:
        # 记录失败日志
        log_query(operation="get_schema", success=False, error=str(e))
        logger.error(f"Failed to retrieve schema: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if cursor:
            cursor.close()
        conn.close()


def get_sensitive_fields() -> list:
    """
    从环境变量获取敏感字段列表
    默认包含基础敏感字段，可通过环境变量SENSITIVE_FIELDS扩展
    """
    default_fields = [
        'password', 'pwd', 'passwd',
        'salary', 'income',
        'ssn', 'social_security',
        'credit_card', 'bank_account',
        'id_number', 'idcard',
        'phone', 'mobile',
        'address', 'email'
    ]
    
    # 从环境变量获取额外的敏感字段
    env_fields = os.environ.get('SENSITIVE_FIELDS', '').split(';')
    env_fields = [field.strip().lower() for field in env_fields if field.strip()]
    
    return env_fields


def is_safe_query(sql: str) -> bool:
    """
    严格检查SQL查询安全性
    允许SELECT语句和WITH开头的查询，并确保没有危险的子查询操作
    支持的格式：
    - SELECT ...
    - WITH ... SELECT ...
    
    同时检查是否包含敏感字段
    """
    # 移除多余的空白字符并转换为小写
    sql = ' '.join(sql.split()).lower()
    
    # 检查是否以select或with开头
    if not (sql.startswith('select') or sql.startswith('with')):
        return False
    
    # 如果以with开头，确保后续包含select
    if sql.startswith('with') and ' select ' not in sql:
        return False
        
    # 检查是否包含危险关键字
    unsafe_keywords = ["insert", "update", "delete", "drop", "alter", "truncate", "create"]
    # 检查整个查询中是否包含危险关键字（可能在子查询中）
    if any(f" {keyword} " in f" {sql} " for keyword in unsafe_keywords):
        return False
        
    # 获取敏感字段列表
    sensitive_fields = get_sensitive_fields()
    
    # 快速检查：如果SQL中包含完整的敏感字段名（考虑单词边界），直接返回False
    for field in sensitive_fields:
        pattern = fr'\b{field}\b'
        if re.search(pattern, sql):
            return False
    
    try:
        # 移除SQL注释
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # 获取select和from之间的内容
        select_pattern = r'select\s+(.*?)\s+from'
        matches = re.findall(select_pattern, sql, re.IGNORECASE)
        
        if matches:
            selected_fields = matches[0].split(',')
            selected_fields = [f.strip().lower() for f in selected_fields]
            
            # 检查每个字段是否是敏感字段
            for field in selected_fields:
                # 处理别名情况 (例如: password as pwd)
                field = field.split(' as ')[0].strip()
                # 处理表前缀情况 (例如: user.password)
                field = field.split('.')[-1].strip()
                
                # 如果是SELECT *，获取表名并检查表结构
                if field == '*':
                    # 提取表名
                    table_pattern = r'from\s+([^\s;]+)'
                    table_match = re.search(table_pattern, sql)
                    if table_match:
                        table_name = table_match.group(1).strip('`')
                        # 获取数据库连接
                        conn = get_connection()
                        try:
                            cursor = conn.cursor()
                            # 获取表的所有字段
                            cursor.execute(f"DESCRIBE `{table_name}`")
                            columns = cursor.fetchall()
                            # 检查是否包含敏感字段
                            for column in columns:
                                field_name = column[0].lower()
                                if field_name in sensitive_fields:
                                    return False
                        finally:
                            cursor.close()
                            conn.close()
                    continue
                    
                # 检查字段名是否完全匹配敏感字段
                if field in sensitive_fields:
                    return False
                    
                # 检查字段是否包含在函数调用中
                for sensitive in sensitive_fields:
                    if f"({sensitive}" in field or f",{sensitive}" in field:
                        return False
    except Exception as e:
        # 如果解析失败，为安全起见返回False
        logger.warning(f"Query parsing failed: {str(e)}")
        return False
        
    return True

def is_sql_injection(query: str) -> bool:
    """
    检查SQL注入的可能性
    仅检查是否包含敏感关键字
    """
    # 常见SQL注入关键词
    injection_keywords = [
        "'", '"', '--', '/*', '*/', 'xp_', 'exec', 'sp_',
        'union select', 'drop table', 'truncate table',
        'insert into', 'update set', 'delete from', 'alter table',
        'create table', 'shutdown', 'waitfor delay'
    ]
    
    # 检查查询中是否包含注入关键词
    query_lower = query.lower()
    for keyword in injection_keywords:
        if keyword in query_lower:
            return True
            
    # 检查是否有可疑的字符串拼接模式
    if re.search(r'\b(and|or)\b\s+\d+\s*=\s*\d+', query_lower):
        return True
        
    if re.search(r'\b(and|or)\b\s+\w+\s*=\s*\w+\s*--', query_lower):
        return True
        
    return False

@mcp.tool()
def query_data(sql: str) -> Dict[str, Any]:
    """Execute read-only SQL queries"""
    if not is_safe_query(sql):
        error_msg = "Potentially unsafe query detected. Only SELECT queries are allowed. No sensitive fields like password/salary/etc."
        log_query(operation=sql, success=False, error=error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    if is_sql_injection(sql):
        error_msg = "Potentially SQL injection detected!"
        log_query(operation=sql, success=False, error=error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    logger.info(f"Executing query: {sql}")
    conn = get_connection()
    cursor = None
    try:
        # Create dictionary cursor
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Start read-only transaction
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("START TRANSACTION")
        
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            conn.commit()

            # 记录成功查询
            log_query(operation=sql, success=True)
            
            # Convert results to serializable format
            return {
                "success": True,
                "results": results,
                "rowCount": len(results)
            }
        except Exception as e:
            conn.rollback()
            error_msg = str(e)
            log_query(operation=sql, success=False, error=error_msg)
            return {
                "success": False,
                "error": str(e)
            }
    finally:
        if cursor:
            cursor.close()
        conn.close()


@mcp.resource("mysql://tables")
def get_tables() -> Dict[str, Any]:
    """Provide database table list"""
    conn = get_connection()
    cursor = None
    try:
        # Create dictionary cursor
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables]
        
        return {
            "database": DB_CONFIG["db"],
            "tables": table_names
        }
    finally:
        if cursor:
            cursor.close()
        conn.close()


@mcp.resource("mysql://table/{table_name}/describe")
def get_table_description(table_name: str) -> Dict[str, Any]:
    """获取指定表的详细描述信息，以CREATE TABLE格式返回"""
    conn = get_connection()
    cursor = None
    try:
        # 创建字典游标
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 检查表是否存在
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables]
        
        if table_name not in table_names:
            return {
                "success": False,
                "error": f"表 '{table_name}' 不存在"
            }
        
        # 获取表结构
        cursor.execute(f"DESCRIBE `{table_name}`")
        columns = cursor.fetchall()
        
        # 获取表的索引信息
        cursor.execute(f"SHOW INDEX FROM `{table_name}`")
        indexes = cursor.fetchall()
        
        # 获取表的其他信息（如注释）
        cursor.execute(f"SHOW TABLE STATUS LIKE '{table_name}'")
        table_status = cursor.fetchone()
        
        # 构建列定义
        column_definitions = []
        for column in columns:
            collation = ""
            if "char" in column["Type"].lower() or "text" in column["Type"].lower():
                collation = ' COLLATE "UTF8MB4_0900_AI_CI"'
            
            definition = f'    "{column["Field"]}" {column["Type"].upper()}{collation}'
            column_definitions.append(definition)
        
        # 构建索引定义
        index_definitions = []
        current_index = None
        current_columns = []
        
        for idx in indexes:
            if current_index != idx["Key_name"]:
                if current_index and current_columns:
                    if current_index == "PRIMARY":
                        index_str = f'Primary key({", ".join(current_columns)})'
                    else:
                        index_str = f'Index {current_index}(`{", ".join(current_columns)}`)'
                    index_definitions.append(index_str)
                current_index = idx["Key_name"]
                current_columns = []
            current_columns.append(idx["Column_name"])
        
        # 处理最后一个索引
        if current_index and current_columns:
            if current_index == "PRIMARY":
                index_str = f'Primary key({", ".join(current_columns)})'
            else:
                index_str = f'Index {current_index}(`{", ".join(current_columns)}`)'
            index_definitions.append(index_str)
        
        # 构建完整的表定义
        table_definition = f'CREATE TABLE `{table_name}`\n(\n'
        table_definition += ',\n'.join(column_definitions)
        table_definition += f'\n) COMMENT "{table_status["Comment"] or "None"}"'
        if index_definitions:
            table_definition += '\n' + '\n'.join(index_definitions)
            
        return {
            "success": True,
            "table_definition": table_definition
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if cursor:
            cursor.close()
        conn.close()


def validate_config():
    """Validate database configuration"""
    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        logger.warning("Using default values, which may not work in production.")


def main():
    validate_config()
    print(f"MySQL MCP server started, connected to {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['db']}")


if __name__ == "__main__":
    mcp.run(transport='stdio')
    # mcp dev run_server.py
    # sql = "select salary from employee limit 3"
    # print(is_sql_injection(sql))
