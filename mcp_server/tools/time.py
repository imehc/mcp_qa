"""
时间相关的MCP工具
提供各种时间操作和格式化功能
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pydantic import BaseModel
import pytz

logger = logging.getLogger(__name__)


class GetCurrentTimeParams(BaseModel):
    """获取当前时间参数"""
    timezone: Optional[str] = None
    format: Optional[str] = None


class FormatTimeParams(BaseModel):
    """格式化时间参数"""
    timestamp: float
    format: Optional[str] = None
    timezone: Optional[str] = None


class ParseTimeParams(BaseModel):
    """解析时间参数"""
    time_string: str
    format: Optional[str] = None
    timezone: Optional[str] = None


class TimeCalculationParams(BaseModel):
    """时间计算参数"""
    base_timestamp: float
    operation: str  # add, subtract
    years: int = 0
    months: int = 0
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0


class TimezoneConvertParams(BaseModel):
    """时区转换参数"""
    timestamp: float
    from_timezone: str
    to_timezone: str


def get_current_time_sync(params: GetCurrentTimeParams) -> Dict[str, Any]:
    """
    获取当前时间
    
    参数:
        params: 包含时区和格式的参数
        
    返回:
        当前时间信息
    """
    try:
        # 获取时区
        tz = None
        if params.timezone:
            try:
                tz = pytz.timezone(params.timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"未知时区: {params.timezone}, 使用上海时区")
                tz = pytz.timezone('Asia/Shanghai')
        else:
            # 默认使用上海时区而不是UTC
            tz = pytz.timezone('Asia/Shanghai')
        
        # 获取当前时间
        now = datetime.now(tz)
        
        # 准备返回数据
        result = {
            "timestamp": now.timestamp(),
            "timezone": str(tz),
            "iso_format": now.isoformat(),
            "utc_timestamp": now.astimezone(pytz.UTC).timestamp(),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "weekday": now.weekday(),
            "weekday_name": now.strftime("%A"),
            "month_name": now.strftime("%B")
        }
        
        # 添加格式化时间
        if params.format:
            try:
                result["formatted"] = now.strftime(params.format)
            except ValueError as e:
                result["format_error"] = str(e)
        else:
            result["formatted"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        
        # 添加中文格式
        result["chinese_format"] = now.strftime("%Y年%m月%d日 %H时%M分%S秒")
        
        return result
        
    except Exception as e:
        logger.error(f"获取当前时间失败: {e}")
        return {"error": f"获取当前时间失败: {str(e)}"}


def format_timestamp_sync(params: FormatTimeParams) -> Dict[str, Any]:
    """
    格式化时间戳
    
    参数:
        params: 包含时间戳、格式和时区的参数
        
    返回:
        格式化后的时间信息
    """
    try:
        # 从时间戳创建datetime对象
        dt = datetime.fromtimestamp(params.timestamp, tz=pytz.UTC)
        
        # 应用时区
        if params.timezone:
            try:
                target_tz = pytz.timezone(params.timezone)
                dt = dt.astimezone(target_tz)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"未知时区: {params.timezone}, 使用上海时区")
                target_tz = pytz.timezone('Asia/Shanghai')
                dt = dt.astimezone(target_tz)
        else:
            # 默认转换为上海时区
            target_tz = pytz.timezone('Asia/Shanghai')
            dt = dt.astimezone(target_tz)
        
        # 准备返回数据
        result = {
            "original_timestamp": params.timestamp,
            "timezone": str(dt.tzinfo),
            "iso_format": dt.isoformat(),
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "minute": dt.minute,
            "second": dt.second,
            "weekday": dt.weekday(),
            "weekday_name": dt.strftime("%A"),
            "month_name": dt.strftime("%B")
        }
        
        # 添加格式化时间
        if params.format:
            try:
                result["formatted"] = dt.strftime(params.format)
            except ValueError as e:
                result["format_error"] = str(e)
        else:
            result["formatted"] = dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        
        # 添加中文格式
        result["chinese_format"] = dt.strftime("%Y年%m月%d日 %H时%M分%S秒")
        
        return result
        
    except Exception as e:
        logger.error(f"格式化时间戳失败: {e}")
        return {"error": f"格式化时间戳失败: {str(e)}"}


def parse_time_string_sync(params: ParseTimeParams) -> Dict[str, Any]:
    """
    解析时间字符串
    
    参数:
        params: 包含时间字符串、格式和时区的参数
        
    返回:
        解析后的时间信息
    """
    try:
        # 常见的时间格式
        common_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y年%m月%d日 %H时%M分%S秒",
            "%Y年%m月%d日",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ]
        
        dt = None
        used_format = None
        
        # 如果指定了格式，优先使用
        if params.format:
            try:
                dt = datetime.strptime(params.time_string, params.format)
                used_format = params.format
            except ValueError:
                logger.warning(f"指定格式解析失败: {params.format}")
        
        # 如果没有指定格式或指定格式失败，尝试常见格式
        if dt is None:
            for fmt in common_formats:
                try:
                    dt = datetime.strptime(params.time_string, fmt)
                    used_format = fmt
                    break
                except ValueError:
                    continue
        
        if dt is None:
            return {
                "error": "无法解析时间字符串",
                "input": params.time_string,
                "tried_formats": common_formats if not params.format else [params.format] + common_formats
            }
        
        # 应用时区信息
        if params.timezone:
            try:
                tz = pytz.timezone(params.timezone)
                if dt.tzinfo is None:
                    dt = tz.localize(dt)
                else:
                    dt = dt.astimezone(tz)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"未知时区: {params.timezone}")
        elif dt.tzinfo is None:
            # 如果没有时区信息，假设为上海时区
            dt = pytz.timezone('Asia/Shanghai').localize(dt)
        
        result = {
            "original_string": params.time_string,
            "used_format": used_format,
            "timestamp": dt.timestamp(),
            "timezone": str(dt.tzinfo),
            "iso_format": dt.isoformat(),
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "minute": dt.minute,
            "second": dt.second,
            "weekday": dt.weekday(),
            "weekday_name": dt.strftime("%A"),
            "month_name": dt.strftime("%B"),
            "formatted": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "chinese_format": dt.strftime("%Y年%m月%d日 %H时%M分%S秒")
        }
        
        return result
        
    except Exception as e:
        logger.error(f"解析时间字符串失败: {e}")
        return {"error": f"解析时间字符串失败: {str(e)}"}


def calculate_time_sync(params: TimeCalculationParams) -> Dict[str, Any]:
    """
    时间计算
    
    参数:
        params: 包含基础时间戳和计算参数
        
    返回:
        计算后的时间信息
    """
    try:
        # 从时间戳创建datetime对象，默认使用上海时区
        base_dt = datetime.fromtimestamp(params.base_timestamp, tz=pytz.timezone('Asia/Shanghai'))
        
        # 创建时间差
        delta = timedelta(
            days=params.days,
            hours=params.hours,
            minutes=params.minutes,
            seconds=params.seconds
        )
        
        # 处理年和月（需要特殊处理）
        if params.years != 0 or params.months != 0:
            # 计算新的年和月
            new_year = base_dt.year + params.years
            new_month = base_dt.month + params.months
            
            # 处理月份溢出
            while new_month > 12:
                new_year += 1
                new_month -= 12
            while new_month < 1:
                new_year -= 1
                new_month += 12
            
            # 处理日期溢出（如果目标月份没有那么多天）
            import calendar
            max_day = calendar.monthrange(new_year, new_month)[1]
            new_day = min(base_dt.day, max_day)
            
            # 创建新的日期
            try:
                base_dt = base_dt.replace(year=new_year, month=new_month, day=new_day)
            except ValueError:
                # 如果仍然有问题，使用月末日期
                base_dt = base_dt.replace(year=new_year, month=new_month, day=max_day)
        
        # 执行计算
        if params.operation == "add":
            result_dt = base_dt + delta
        elif params.operation == "subtract":
            result_dt = base_dt - delta
        else:
            return {"error": f"不支持的操作: {params.operation}"}
        
        # 计算时间差
        time_diff = result_dt - base_dt
        
        result = {
            "base_timestamp": params.base_timestamp,
            "base_time": base_dt.isoformat(),
            "operation": params.operation,
            "calculation": {
                "years": params.years,
                "months": params.months,
                "days": params.days,
                "hours": params.hours,
                "minutes": params.minutes,
                "seconds": params.seconds
            },
            "result_timestamp": result_dt.timestamp(),
            "result_time": result_dt.isoformat(),
            "difference_seconds": time_diff.total_seconds(),
            "difference_days": time_diff.days,
            "formatted_result": result_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "chinese_result": result_dt.strftime("%Y年%m月%d日 %H时%M分%S秒")
        }
        
        return result
        
    except Exception as e:
        logger.error(f"时间计算失败: {e}")
        return {"error": f"时间计算失败: {str(e)}"}


def convert_timezone_sync(params: TimezoneConvertParams) -> Dict[str, Any]:
    """
    时区转换
    
    参数:
        params: 包含时间戳和源、目标时区的参数
        
    返回:
        转换后的时间信息
    """
    try:
        # 获取源时区和目标时区
        from_tz = pytz.timezone(params.from_timezone)
        to_tz = pytz.timezone(params.to_timezone)
        
        # 从时间戳创建datetime对象，并应用源时区
        dt = datetime.fromtimestamp(params.timestamp, tz=from_tz)
        
        # 转换到目标时区
        converted_dt = dt.astimezone(to_tz)
        
        result = {
            "original_timestamp": params.timestamp,
            "from_timezone": params.from_timezone,
            "to_timezone": params.to_timezone,
            "original_time": dt.isoformat(),
            "converted_time": converted_dt.isoformat(),
            "converted_timestamp": converted_dt.timestamp(),
            "original_formatted": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "converted_formatted": converted_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "original_chinese": dt.strftime("%Y年%m月%d日 %H时%M分%S秒"),
            "converted_chinese": converted_dt.strftime("%Y年%m月%d日 %H时%M分%S秒"),
            "time_difference_hours": (converted_dt.utcoffset() - dt.utcoffset()).total_seconds() / 3600
        }
        
        return result
        
    except pytz.exceptions.UnknownTimeZoneError as e:
        return {"error": f"未知时区: {str(e)}"}
    except Exception as e:
        logger.error(f"时区转换失败: {e}")
        return {"error": f"时区转换失败: {str(e)}"}


def get_available_timezones() -> Dict[str, Any]:
    """
    获取可用的时区列表
    
    返回:
        时区信息
    """
    try:
        # 获取所有时区
        all_timezones = list(pytz.all_timezones)
        
        # 常用时区
        common_timezones = [
            'UTC',
            'US/Eastern',
            'US/Central',
            'US/Mountain',
            'US/Pacific',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Asia/Shanghai',
            'Asia/Tokyo',
            'Asia/Seoul',
            'Asia/Kolkata',
            'Australia/Sydney',
            'Australia/Melbourne'
        ]
        
        # 中国时区
        china_timezones = [
            'Asia/Shanghai',
            'Asia/Chongqing',
            'Asia/Harbin',
            'Asia/Urumqi'
        ]
        
        result = {
            "total_count": len(all_timezones),
            "common_timezones": common_timezones,
            "china_timezones": china_timezones,
            "all_timezones": sorted(all_timezones)[:100],  # 只返回前100个，避免响应过大
            "note": "完整的时区列表已截断，如需特定时区请查询"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"获取时区列表失败: {e}")
        return {"error": f"获取时区列表失败: {str(e)}"}


def get_time_info() -> Dict[str, Any]:
    """
    获取时间相关的系统信息
    
    返回:
        时间系统信息
    """
    try:
        now_utc = datetime.now(pytz.UTC)
        now_local = datetime.now()
        now_shanghai = datetime.now(pytz.timezone('Asia/Shanghai'))
        
        result = {
            "utc_time": now_utc.isoformat(),
            "local_time": now_local.isoformat(),
            "shanghai_time": now_shanghai.isoformat(),
            "utc_timestamp": now_utc.timestamp(),
            "local_timestamp": now_local.timestamp(),
            "shanghai_timestamp": now_shanghai.timestamp(),
            "system_timezone": str(now_local.astimezone().tzinfo),
            "default_timezone": "Asia/Shanghai",
            "utc_offset_hours": now_local.astimezone().utcoffset().total_seconds() / 3600,
            "is_dst": bool(now_local.astimezone().dst()),
            "available_formats": [
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y年%m月%d日 %H时%M分%S秒",
                "%B %d, %Y %H:%M:%S",
                "%d %B %Y %H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%A, %B %d, %Y"
            ]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"获取时间信息失败: {e}")
        return {"error": f"获取时间信息失败: {str(e)}"}


def register_time_tools(mcp):
    """注册时间工具到MCP"""
    
    @mcp.tool()
    async def get_current_time(params: dict):
        """获取当前时间"""
        return get_current_time_sync(GetCurrentTimeParams(**params))
    
    @mcp.tool()
    async def format_timestamp(params: dict):
        """格式化时间戳"""
        return format_timestamp_sync(FormatTimeParams(**params))
    
    @mcp.tool()
    async def parse_time_string(params: dict):
        """解析时间字符串"""
        return parse_time_string_sync(ParseTimeParams(**params))
    
    @mcp.tool()
    async def calculate_time(params: dict):
        """时间计算"""
        return calculate_time_sync(TimeCalculationParams(**params))
    
    @mcp.tool()
    async def convert_timezone(params: dict):
        """时区转换"""
        return convert_timezone_sync(TimezoneConvertParams(**params))


# 测试函数
def test_time_tools():
    """测试时间工具"""
    try:
        # 测试获取当前时间
        result = get_current_time_sync(GetCurrentTimeParams())
        assert "timestamp" in result
        
        # 测试格式化时间戳
        result = format_timestamp_sync(FormatTimeParams(timestamp=1234567890.0))
        assert "formatted" in result
        
        # 测试解析时间字符串
        result = parse_time_string_sync(ParseTimeParams(time_string="2023-01-01 12:00:00"))
        assert "timestamp" in result
        
        logger.info("时间工具测试通过")
        
    except Exception as e:
        logger.error(f"时间工具测试失败: {e}")
        raise


if __name__ == "__main__":
    test_time_tools()