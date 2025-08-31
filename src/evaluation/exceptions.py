#!/usr/bin/env python3
"""
评估模块异常定义
"""

class WeightsSchemaError(ValueError):
    """权重模式错误"""
    pass

class ScoringChannelError(RuntimeError):
    """评分通道错误"""
    pass

class DataAuditError(ValueError):
    """数据审计错误"""
    pass
