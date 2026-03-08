#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL实例健康巡检脚本

基于火山引擎文档:
- GetMetricData API: https://www.volcengine.com/docs/6408/105542
- Python SDK: https://www.volcengine.com/docs/6408/170945

功能:
1. 获取指定时间范围内MySQL实例的监控数据
2. 分析性能趋势和识别瓶颈
3. 计算健康评分
4. 生成结构化巡检报告
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import statistics

# 火山引擎 SDK
import volcenginesdkcore
import volcenginesdkrdsmysqlv2
import volcenginesdkcloudmonitor
from volcenginesdkcore.rest import ApiException


class MySQLInstanceInfoCollector:
    """MySQL实例信息采集器"""

    # 云监控命名空间
    NAMESPACE = "VCM_RDS_MySQL"

    # 核心监控指标列表
    METRIC_DEFINITIONS = {
        "cpu": {
            "name": "CpuUtil",
            "display_name": "CPU使用率",
            "unit": "%",
            "description": "实例CPU使用率",
            "sub_namespace": "resource_monitor_new",
        },
        "memory": {
            "name": "MemUtil",
            "display_name": "内存使用率",
            "unit": "%",
            "description": "实例内存使用率",
            "sub_namespace": "resource_monitor_new",
        },
        "disk_util": {
            "name": "DiskUtil",
            "display_name": "磁盘使用率",
            "unit": "%",
            "description": "磁盘空间使用百分比",
            "sub_namespace": "resource_monitor_new",
        },
        "qps": {
            "name": "QPS",
            "display_name": "每秒查询数",
            "unit": "Count/s",
            "description": "每秒查询请求数",
            "sub_namespace": "engine_monitor",
        },
        "tps": {
            "name": "TPS",
            "display_name": "每秒事务数",
            "unit": "Count/s",
            "description": "每秒事务处理数",
            "sub_namespace": "engine_monitor",
        },
        "replication_delay": {
            "name": "ReplicationDelay",
            "display_name": "主从延迟",
            "unit": "Seconds",
            "description": "主从复制延迟时间",
            "sub_namespace": "deploy_monitor_new",
        },
        "IOPSRate": {
            "name": "IOPSRate",
            "display_name": "IOPS",
            "unit": "Count/s",
            "description": "每秒IO次数",
            "sub_namespace": "resource_monitor_new",
        },
        "network_in": {
            "name": "NetworkReceiveThroughput",
            "display_name": "网络入流量",
            "unit": "Bytes/s",
            "description": "每秒网络接收字节数",
            "sub_namespace": "resource_monitor_new",
        },
        "network_out": {
            "name": "NetworkTransmitThroughput",
            "display_name": "网络出流量",
            "unit": "Bytes/s",
            "description": "每秒网络发送字节数",
            "sub_namespace": "resource_monitor_new",
        },
    }

    def __init__(
        self,
        ak: Optional[str] = None,
        sk: Optional[str] = None,
        region: str = "cn-shanghai",
    ):
        """
        初始化采集器

        Args:
            ak: Access Key ID，必填
            sk: Secret Access Key，必填
            region: 区域，默认cn-shanghai
        """
        self.ak = ak
        self.sk = sk
        self.region = region

        if not self.ak or not self.sk:
            raise ValueError("必须通过 --ak 和 --sk 参数传入访问凭证")

        # 初始化RDS MySQL客户端
        self._init_rds_client()

        # 初始化云监控客户端（用于GetMetricData）
        self._init_cloudmonitor_client()

    def _init_rds_client(self):
        """初始化RDS MySQL客户端"""
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = self.ak
        configuration.sk = self.sk
        configuration.region = self.region

        volcenginesdkcore.Configuration.set_default(configuration)
        self.rds_client = volcenginesdkrdsmysqlv2.RDSMYSQLV2Api(
            volcenginesdkcore.ApiClient(configuration)
        )

    def _init_cloudmonitor_client(self):
        """初始化云监控客户端"""
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = self.ak
        configuration.sk = self.sk
        configuration.region = self.region

        volcenginesdkcore.Configuration.set_default(configuration)
        self.cloudmonitor_client = volcenginesdkcloudmonitor.CLOUDMONITORApi(
            volcenginesdkcore.ApiClient(configuration)
        )

    def get_instance_detail(self, instance_id: str) -> Dict[str, Any]:
        """
        获取实例详细信息（规格、版本、参数等）

        Args:
            instance_id: 实例ID

        Returns:
            实例详细信息字典
        """
        try:
            request = volcenginesdkrdsmysqlv2.DescribeDBInstanceDetailRequest(
                instance_id=instance_id
            )

            response = self.rds_client.describe_db_instance_detail(request)

            if hasattr(response, "basic_info") and response.basic_info:
                info = response.basic_info
                result = {
                    "instance_id": instance_id,
                    "instance_name": getattr(info, "instance_name", ""),
                    "instance_status": getattr(info, "instance_status", ""),
                    "db_engine": "MySQL",
                    "db_engine_version": getattr(info, "db_engine_version", ""),
                    "instance_type": getattr(info, "instance_type", ""),
                    "node_spec": getattr(info, "node_spec", ""),
                    "node_number": getattr(info, "node_number", 0),
                    "vcpu": getattr(info, "vcpu", 0),
                    "memory": getattr(info, "memory", 0),
                    "storage_space": getattr(info, "storage_space", 0),
                    "storage_type": getattr(info, "storage_type", ""),
                    "storage_use": getattr(info, "storage_use", 0),
                    "vpc_id": getattr(info, "vpc_id", ""),
                    "subnet_id": getattr(info, "subnet_id", ""),
                    "zone_id": getattr(info, "zone_id", ""),
                    "region_id": getattr(info, "region_id", self.region),
                    "create_time": getattr(info, "create_time", ""),
                    "update_time": getattr(info, "update_time", ""),
                    "project_name": getattr(info, "project_name", ""),
                    "tags": getattr(info, "tags", []),
                    "data_sync_mode": getattr(info, "data_sync_mode", ""),
                    "time_zone": getattr(info, "time_zone", ""),
                }

                # 提取计费信息
                if hasattr(response, "charge_detail") and response.charge_detail:
                    charge = response.charge_detail
                    result["charge_type"] = getattr(charge, "charge_type", "")

                return result

            return {"instance_id": instance_id, "error": "无法获取实例基本信息"}

        except ApiException as e:
            return {
                "instance_id": instance_id,
                "error": f"API调用失败: {e.status} - {e.reason}",
                "error_body": str(e.body) if hasattr(e, "body") else None,
            }
        except Exception as e:
            return {"instance_id": instance_id, "error": f"获取实例信息异常: {str(e)}"}

    def _call_get_metric_data(
        self,
        metric_name: str,
        instance_id: str,
        start_time: int,
        end_time: int,
        period: str = "1m",
        sub_namespace: str = "resource_monitor_new",
    ) -> Dict[str, Any]:
        """
        调用GetMetricData API获取监控数据

        基于文档: https://www.volcengine.com/docs/6408/105542

        Args:
            metric_name: 指标名称
            instance_id: 实例ID
            start_time: 开始时间（秒级时间戳）
            end_time: 结束时间（秒级时间戳）
            period: 聚合周期，支持 1m, 5m, 1h, 1d 等
            sub_namespace: 子命名空间

        Returns:
            监控数据
        """
        try:
            request = volcenginesdkcloudmonitor.GetMetricDataRequest(
                start_time=start_time,
                end_time=end_time,
                namespace=self.NAMESPACE,
                sub_namespace=sub_namespace,
                metric_name=metric_name,
                period=period,
                instances=[
                    volcenginesdkcloudmonitor.InstanceForGetMetricDataInput(
                        dimensions=[
                            volcenginesdkcloudmonitor.DimensionForGetMetricDataInput(
                                name="ResourceID", value=instance_id
                            )
                        ]
                    )
                ],
            )

            response = self.cloudmonitor_client.get_metric_data(request)
            return response

        except ApiException as e:
            return {
                "error": f"获取监控数据失败: {e.status} - {e.reason}",
                "metric_name": metric_name,
                "error_body": str(e.body) if hasattr(e, "body") else None,
            }
        except Exception as e:
            return {
                "error": f"获取监控数据失败: {str(e)}",
                "metric_name": metric_name,
                "error_type": type(e).__name__,
            }

    def _parse_metric_response(self, response) -> List[Dict[str, Any]]:
        """
        解析云监控API返回的response对象，提取干净的数据点

        Args:
            response: SDK返回的response对象

        Returns:
            按节点分组的数据列表，每组包含 node_name, dimensions, data_points
        """
        nodes = []
        try:
            # 获取 metric_data_results
            data_attr = getattr(response, "data", None)
            if data_attr is None:
                return nodes

            metric_data_results = getattr(data_attr, "metric_data_results", None)
            if not metric_data_results:
                return nodes

            for result in metric_data_results:
                node_info = {
                    "legend": getattr(result, "legend", ""),
                    "dimensions": {},
                    "data_points": [],
                }

                # 提取维度信息
                dims = getattr(result, "dimensions", [])
                if dims:
                    for dim in dims:
                        name = getattr(dim, "name", "")
                        value = getattr(dim, "value", "")
                        node_info["dimensions"][name] = value

                # 提取数据点，精简格式
                data_points = getattr(result, "data_points", [])
                if data_points:
                    for dp in data_points:
                        ts = getattr(dp, "timestamp", 0)
                        val = getattr(dp, "value", 0)
                        node_info["data_points"].append(
                            {
                                "ts": ts,
                                "time": (
                                    datetime.fromtimestamp(ts).strftime(
                                        "%Y-%m-%d %H:%M"
                                    )
                                    if ts
                                    else ""
                                ),
                                "value": round(val, 4) if val is not None else None,
                            }
                        )

                nodes.append(node_info)

        except Exception as e:
            nodes.append({"error": f"解析响应失败: {str(e)}"})

        return nodes

    def get_metric_data(
        self,
        instance_id: str,
        metric_key: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "1m",
    ) -> Dict[str, Any]:
        """
        获取单个监控指标数据

        Args:
            instance_id: 实例ID
            metric_key: 指标键 (如 "cpu", "memory" 等)
            start_time: 开始时间
            end_time: 结束时间
            period: 聚合周期

        Returns:
            监控数据（已解析为干净的JSON结构）
        """
        if metric_key not in self.METRIC_DEFINITIONS:
            return {"error": f"不支持的指标: {metric_key}"}

        metric = self.METRIC_DEFINITIONS[metric_key]

        # 转换为秒级时间戳
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        # 获取指标对应的sub_namespace
        sub_namespace = metric.get("sub_namespace", "resource_monitor_new")

        response = self._call_get_metric_data(
            metric_name=metric["name"],
            instance_id=instance_id,
            start_time=start_ts,
            end_time=end_ts,
            period=period,
            sub_namespace=sub_namespace,
        )

        # 如果返回的是错误字典，直接使用
        if isinstance(response, dict) and "error" in response:
            return {
                "metric_key": metric_key,
                "metric_name": metric["name"],
                "display_name": metric["display_name"],
                "unit": metric["unit"],
                "error": response["error"],
            }

        # 解析SDK response对象，提取干净的数据
        parsed_nodes = self._parse_metric_response(response)

        result = {
            "metric_key": metric_key,
            "metric_name": metric["name"],
            "display_name": metric["display_name"],
            "unit": metric["unit"],
            "node_count": len(parsed_nodes),
            "nodes": parsed_nodes,
        }

        # 计算汇总统计
        all_values = []
        for node in parsed_nodes:
            for dp in node.get("data_points", []):
                if dp.get("value") is not None:
                    all_values.append(dp["value"])

        if all_values:
            result["summary"] = {
                "data_point_count": len(all_values),
                "min": round(min(all_values), 4),
                "max": round(max(all_values), 4),
                "avg": round(statistics.mean(all_values), 4),
            }

        return result

    def get_all_metrics(
        self,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "5m",
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        获取所有（或指定的）监控指标数据

        Args:
            instance_id: 实例ID
            start_time: 开始时间
            end_time: 结束时间
            period: 聚合周期，默认5分钟
            metrics: 要获取的指标列表，默认获取全部

        Returns:
            所有监控数据汇总
        """
        if metrics is None:
            metrics = list(self.METRIC_DEFINITIONS.keys())

        results = {}
        for metric_key in metrics:
            results[metric_key] = self.get_metric_data(
                instance_id=instance_id,
                metric_key=metric_key,
                start_time=start_time,
                end_time=end_time,
                period=period,
            )
            # 避免触发API限流（1秒20次）
            time.sleep(0.1)

        return {
            "instance_id": instance_id,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "period": period,
            "metrics": results,
        }

    def get_comprehensive_info(
        self,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "5m",
    ) -> Dict[str, Any]:
        """
        获取实例综合信息（基础配置 + 监控数据），按指标分组返回

        Args:
            instance_id: 实例ID
            start_time: 监控数据开始时间
            end_time: 监控数据结束时间
            period: 监控数据聚合周期

        Returns:
            包含公共信息和按指标分组数据的字典:
            {
                "common": { collection_time, instance_id, time_range, instance_detail },
                "metrics": { "cpu": {...}, "memory": {...}, ... }
            }
        """
        common_info = {
            "collection_time": datetime.now().isoformat(),
            "instance_id": instance_id,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "instance_detail": self.get_instance_detail(instance_id),
        }

        # 获取核心监控指标
        core_metrics = [
            "cpu",
            "memory",
            "disk_util",
            "qps",
            "tps",
            "replication_delay",
            "IOPSRate",
            "network_in",
            "network_out",
        ]
        metrics_data = {}
        for metric_key in core_metrics:
            metric_result = self.get_metric_data(
                instance_id=instance_id,
                metric_key=metric_key,
                start_time=start_time,
                end_time=end_time,
                period=period,
            )
            metrics_data[metric_key] = metric_result
            # 避免触发API限流（1秒20次）
            time.sleep(0.1)

        return {
            "common": common_info,
            "metrics": metrics_data,
            "resource_meta": {
                "instance_id": instance_id,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "period": period,
            },
        }


def main():
    """主函数 - 演示用法"""
    import argparse

    default_output_dir = r"D:\Study\python\agent\maintenance-agent\metric_data"

    parser = argparse.ArgumentParser(
        description="获取MySQL实例基础配置和监控信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取实例详情
  python get_instance_info.py --instance-id mysql-d4f6a32d4e06 --ak <ak> --sk <sk> --action detail
  
  # 获取最近1小时的监控数据
  python get_instance_info.py --instance-id mysql-d4f6a32d4e06 --ak <ak> --sk <sk> --action metrics --hours 1
  
  # 获取综合信息
  python get_instance_info.py --instance-id mysql-d4f6a32d4e06 --action all \\
      --ak <ak> --sk <sk> \\
      --start "2026-02-07 00:00" --end "2026-02-07 12:00"
        """,
    )

    parser.add_argument("--instance-id", required=True, help="MySQL实例ID")
    parser.add_argument(
        "--ak",
        required=True,
        help="火山引擎访问密钥ID（Access Key）",
    )
    parser.add_argument(
        "--sk",
        required=True,
        help="火山引擎访问密钥Secret（Secret Key）",
    )
    parser.add_argument(
        "--action",
        choices=["detail", "metrics", "all"],
        default="all",
        help="操作类型: detail=实例详情, metrics=监控数据, all=全部",
    )
    parser.add_argument("--start", help="开始时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--end", help="结束时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument(
        "--hours", type=int, default=1, help="查询最近N小时的数据（如未指定start/end）"
    )
    parser.add_argument(
        "--period", default="5m", help="监控数据聚合周期 (1m, 5m, 1h, 1d)"
    )
    parser.add_argument("--region", default="cn-shanghai", help="区域")
    parser.add_argument("--output", help="输出文件路径（JSON格式）")

    args = parser.parse_args()

    # 解析时间范围
    if args.start and args.end:
        start_time = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(args.end, "%Y-%m-%d %H:%M")
    else:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=args.hours)

    # 初始化采集器
    collector = MySQLInstanceInfoCollector(ak=args.ak, sk=args.sk, region=args.region)

    # 执行操作
    if args.action == "detail":
        result = collector.get_instance_detail(args.instance_id)

    elif args.action == "metrics":
        result = collector.get_all_metrics(
            instance_id=args.instance_id,
            start_time=start_time,
            end_time=end_time,
            period=args.period,
        )
    else:  # all
        result = collector.get_comprehensive_info(
            instance_id=args.instance_id,
            start_time=start_time,
            end_time=end_time,
            period=args.period,
        )

    output_dir = default_output_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_base_name = f"{args.instance_id}_{args.action}_{timestamp}"

    if args.output:
        output_dir = os.path.dirname(args.output) or "."
        base_name = os.path.splitext(os.path.basename(args.output))[0]
    else:
        base_name = default_base_name

    os.makedirs(output_dir, exist_ok=True)

    if args.action == "all":
        common_info = result["common"]
        resource_meta = result["resource_meta"]
        saved_files = []

        for metric_key, metric_data in result["metrics"].items():
            file_data = {
                "collection_time": common_info["collection_time"],
                "instance_id": common_info["instance_id"],
                "time_range": common_info["time_range"],
                "instance_detail": common_info["instance_detail"],
                "resource_metrics": {
                    "instance_id": resource_meta["instance_id"],
                    "time_range": resource_meta["time_range"],
                    "period": resource_meta["period"],
                    "metrics": {metric_key: metric_data},
                },
            }

            file_path = os.path.join(output_dir, f"{base_name}_{metric_key}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(file_data, f, ensure_ascii=False, indent=2, default=str)
            saved_files.append(file_path)
            print(f"已保存指标 [{metric_key}] 到: {file_path}")

        print(f"\n共生成 {len(saved_files)} 个文件")
    else:
        output_json = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        file_path = (
            args.output
            if args.output
            else os.path.join(output_dir, f"{base_name}.json")
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"结果已保存到: {file_path}")

    return result


if __name__ == "__main__":
    main()
