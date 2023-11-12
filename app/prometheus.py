# Differences of this module to prometheus_client library
# - Acts only as a formatter for Prometheus exposition data format.
#   It does not implement a web server for Prometheus to scrape metrics from. We push metrics to VictoriaMetrics.
# - Implements only Prometheus data types that are needed by this project.
# - Allows setting Counter to given (monotonic) value instead of only allowing to incrementing it by one.
#   This is required for energy meter counters that are directly read from the meter.
# - Allows setting the optional timestamp parameter for each metric, which is needed when polling
#   the car data and electricity prices, which may contain data that was already scraped last time.


from typing import Dict, List, Optional


class Samples(object):
    def __init__(self, labels):
        self.common_labels_for_all_samples = labels if labels else {}
        self.samples = []

    def add(self, value: float, labels: Optional[Dict[str, str]] = None, timestamp_msec: Optional[float] = None):
        self.samples.append(
            {
                "value": round(value, 3),
                "labels": labels if labels else {},
                "timestamp": timestamp_msec,
            }
        )

    def format(self) -> List[str]:
        output = []
        for sample in self.samples:
            s = ""
            labels = {**self.common_labels_for_all_samples, **sample["labels"]}
            if labels:
                labels_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
                s += f"{{{labels_str}}} "

            s += f"{sample['value']}"

            if sample["timestamp"]:
                s += f" {sample['timestamp']}"

            output.append(s)
        return output


class Metrics(object):
    def __init__(self):
        self.samples = []

    def counter(self, name: str, description: str, labels: Optional[Dict[str, str]] = None) -> Samples:
        s = Samples(labels)
        self.samples.append(
            {
                "type": "counter",
                "name": name,
                "description": description,
                "samples": s,
            }
        )
        return s

    def gauge(self, name: str, description: str, labels: Optional[Dict[str, str]] = None) -> Samples:
        s = Samples(labels)
        self.samples.append(
            {
                "type": "gauge",
                "name": name,
                "description": description,
                "samples": s,
            }
        )
        return s

    def format(self) -> str:
        report = ""
        for sample in self.samples:
            report += f"# HELP {sample['name']} {sample['description']}\n"
            report += f"# TYPE {sample['name']} {sample['type']}\n"
            for s in sample["samples"].format():
                report += f"{sample['name']} {s}\n"
        return report
