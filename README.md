# Self Service Portal Exporter

## Overview
This exporter is designed to export balance value from Self Service Portals and store it in [TSDB](https:///) database (native, 3rd-party). Existing exporter provider modules are prepared for:
* [Almatel (Russia)](https://almatel.ru/), Internet Service Provider
* [Aruba Cloud](https://arubacloud.com/), Cloud Service Provider
* [Freedom-VRN](https://freedom-vrn.ru), Internet Service Provider
* [MegaFon B2C (Russia)](https://megafon.ru/), Service Provider
* ~~[T2 B2C (Russia)](https://T2.ru/), Service Provider~~, _dysfunctional since mid-2024 due to introduced strict 2FA with OTP over Email or SMS_ 
* [Vultr](https://vultr.com/), Cloud Service Provider
* [Wifire (Russia)](https://wifire.ru/), Internet Service Provider

## Design
#### Simplified System Design
![SSP Exporter System Design](images/ssp_exporter_system_design.png)

#### Workflow
```mermaid
flowchart TB
    Step1(Load configuration) --> Step2(Validate configuration)
    Step2 --> Step3(Load providers)
    Step3 --> Step4(Schedule async provider jobs)
    subgraph onetime_run ["<div style="width:12em; display:flex; justify-content: flex-end;">Run once</div>"]
      Step5(Run provider jobs first time)
    end
    Step3 --> Step5
    Step5 --> Step8
    Step4 --> Step7
    subgraph scheduler_loop ["<div style="width:12em; display:flex; justify-content: flex-end;">On schedule</div>"]
        Step7(Run provider's configuration by a timer)--> Step8(Collect data)
        Step8 --> Step6(Store collected data)
    end
    Step6 --> Step9
    subgraph metrics_loop ["<div style="width:12em; display:flex; justify-content: flex-end;">On demand</div>"]
        Step9(Publish metrics with collected data)
    end
```

At startup, the exporter configuration is validated against [JSON schema](https://json-schema.org/), then the exporter reads `providers` directory with modules, loads them one by one, schedules jobs for the `update_balance()` function from each provider, and triggers the first collection attempt. The [Prometheus Client](https://github.com/prometheus/client_python) dynamically registers [GaugeMetricsFamily](https://github.com/prometheus/client_python#custom-collectors) metrics using labels from the corresponding configuration.

On the monitoring side, the collected metrics values are scraped by a [collector](https://prometheus.io/docs/instrumenting/writing_exporters/#collectors) compatible with the [Prometheus metric format](https://prometheus.io/), and stored in a [TSDB](https://en.wikipedia.org/wiki/Time_series_database). Later the collected data is represented via dashboards, e.g. [Grafana](https://grafana.com).

#### Metrics sample

```
...
# HELP ssp_balance AlmatelRussia
# TYPE ssp_balance gauge
ssp_balance{category="SP",currency="₽",description="Almatel RegionCode1",identifier="user123456",poll_interval="30m",provider="AlmatelRussia"} 387.32
# HELP ssp_balance ArubaCloud
# TYPE ssp_balance gauge
ssp_balance{category="Hosting",currency="€",description="ArubaCloud RegionCode1",identifier="1234566@aruba.it",poll_interval="30m",provider="ArubaCloud"} 19.78
# HELP ssp_balance MegafonRussiaB2C
# TYPE ssp_balance gauge
ssp_balance{category="SP",currency="₽",description="Megafon User1",identifier="79201234567",poll_interval="30m",provider="MegafonRussiaB2C"} 790.1
# HELP ssp_balance Vultr
# TYPE ssp_balance gauge
ssp_balance{category="Hosting",currency="$",description="Vultr RegionCode1",identifier="username@domain.tld",poll_interval="30m",provider="Vultr"} 13.32
# HELP ssp_balance WifireRussia
# TYPE ssp_balance gauge
ssp_balance{category="SP",currency="₽",description="Wifire RegionCode1",identifier="123456",poll_interval="30m",provider="WifireRussia"} 172.05
```

## Application Settings
The exporter requires 2 types of configuration:
* Configuration file with defined accounts of data providers
* JSON schema for configuration file format validation

Configuration files can be JSON or YAML format, the code will detect file type based on extension: .json, .yaml or .yml.

#### Configuration File
Configuration file contains 2 top sections: `service` and `identifiers`.
The `service` section defines `metric_name`, possible `messages` encoded in the target values, and list of available `user_agents` to randomly select during each provider initialization. Message names are used in the provider's code, see [Writing a Custom Provider](#writing-a-custom-provider) chapter.
Sample in YAML representation:
```yaml
service:
  metric_name: ssp_balance
  messages:
    init: -1000000
    disabled: -1000001
    no_answer: -1000002
    captcha: -1000003
    cannot_proceed: -1000004
    rate_limit: -1000005
    parsing_error: -1000006
    connection_error: -1000007
  user_agents:
    - Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.33
    - Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36
    - Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0
    - Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36
    - Mozilla/5.0 (X11; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0
    - Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0
```

The `identifiers` section contains a list of available identifiers for each existing provider:
Key | Description | Mandatory | Type | Default Value
 -- | -- | -- | -- | --
identifier | Username or client ID to access Self Service Portal | Yes | String | No
password | Password or secret to access Self Service Portal | Yes | String | No
labels | Dictionary of additional labels in key:value format | No | String:Boolean \| Integer \| Float \| String | No
tls_verify | Whether to check TLS certificate against trusted certificate authorities | No | Boolean | False
poll_interval | Integer in seconds of interval for polling via scheduler | No | Integer | 3600
disabled | Prevent data collection | No | Boolean | False

Sample in YAML representation:
```yaml
identifiers:
  ProviderName:
    - identifier: provider_identifier
      password: provider_password
      labels:
        key1: value1
        key2: value2
        keyN: valueN
      poll_interval: 1800
```

#### JSON Schema File
**TBD**

####  Environmental Augmentation

Since the exporter initially was designed to be containerized, some settings can be overriden by environment variables or command line arguments.

Argument Name | Variable Name | Description | Default Value
-- | -- | -- | --
--config, -c | SSP_EXPORTER_CONFIG_FILE | Path to configuration file | ./config/production_exporter.yaml
--schema, -s | SSP_EXPORTER_SCHEMA_FILE | Path to JSON schema | ./config/schema.json
--address, -a | SSP_EXPORTER_BIND_ADDRESS | Network address to bind server | localhost
--port, -p | SSP_EXPORTER_BIND_PORT | Network port to bind server | 10032
--loglevel, -l | SSP_EXPORTER_LOG_LEVEL | Set logging level.<br/>Possible values: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL | INFO

## Data Visualization
#### Available Return Codes

To distinguish balance values from possible errors, special mnemonic codes used, which can be easily extended by [`service` section of the Configuration file](#configuration-file):

Value | Description 
-- | -- 
-1000000 | Init state
-1000001 | Disabled
-1000002 | No Answer
-1000003 | Captcha
-1000004 | Cannot Log In
-1000005 | Rate Limit
-1000006 | Parsing Error
-1000007 | Connection Error

#### Grafana
To decode these values into human-readable statuses, Grafana's dashboard must have the following override configuration:

```json
...
  "overrides": [
    {
      "matcher": {
        "id": "byName",
        "options": "Value"
      },
      "properties": [
        {
          "id": "mappings",
          "value": [
            {
              "options": {
                "-1000000": {
                  "color": "#c8f7c1",
                  "index": 0,
                  "text": "Initialized"
                },
                "-1000001": {
                  "color": "#5c00a1",
                  "index": 1,
                  "text": "Disabled"
                },
                "-1000002": {
                  "color": "dark-red",
                  "index": 2,
                  "text": "No Answer"
                },
                "-1000003": {
                  "color": "yellow",
                  "index": 3,
                  "text": "Captcha"
                },
                "-1000004": {
                  "color": "purple",
                  "index": 4,
                  "text": "Cannot Proceed"
                },
                "-1000005": {
                  "color": "dark-blue",
                  "index": 5,
                  "text": "Rate Limit"
                },
                "-1000006": {
                  "color": "orange",
                  "index": 6,
                  "text": "Parsing Error"
                },
                "-1000007": {
                  "color": "#7d0000",
                  "index": 7,
                  "text": "Connection Error"
                }
              },
              "type": "value"
            }
          ]
        }
      ]
    }
  ]
...
```

#### Panels
Visualization as `Stat` panels:
![Grafana Dashboard Sample](images/grafana_dashboard_sample-1.png)

Visualization as `Table` panels:
![Grafana Dashboard Sample](images/grafana_dashboard_sample-2.png)

## Writing a Custom Provider

To write your own provider, you need to create a new one Python file under the `providers` directory, name it with a snake-case like `<module_name>.py` where `<module_name>` must be replaced with a real module name.

The module must have the following skeleton:

```python

""" ProviderName exporter module """

from dataclasses import dataclass, InitVar

import json

<<
import required modules
>>

from logger import Logger

@dataclass
class ProviderName:
    """ ProviderName exporter class """

    class_type: str = 'provider'
    messages: list[str] = None
    user_agent: str = None
    identifier: str = None
    labels: dict[str, (str, int, float)] = None
    password: str = None
    disabled: bool = False
    tls_verify: bool = False
    poll_interval: int = 3600
    last_balance: float = None
    log_level: InitVar[int] = 20

    def __post_init__(self, log_level: int = 20) -> None:
        self._lgr = Logger(
            log_level=log_level, class_name=self.__class__.__name__)

    def __str__(self) -> str:
        """ Human readable print of the current class """

        return_obj = {}

        for key, value in self.__dict__.items():
            if isinstance(value, bool | int | float | str | dict | list | None):
                return_obj[key] = {
                    'value': value,
                    'type': type(value).__name__
                }

        return json.dumps(return_obj, ensure_ascii=False, indent=4)

    def as_dict(self) -> dict:
        """ Return current class as a dictionary """

        self_dict = {}

        for key, value in self.__dict__.items():
            if isinstance(value, bool | int | float | str | dict | list | None):
                self_dict[key]=value

        return self_dict

    def get_balance(self) -> float | int:
        """ Return last balance """

        return self.last_balance

    def update_balance(self) -> None:
        """ Collect current balance for identifier """

        <<
        
        code to collect data from a remote endpoint

        it must also set the `self.last_balance` variable to a float value of
        the collected data, e.g.

        self.last_balance = float(balance)

        or to appropriate service message if some error happened, i.e.

        self.last_balance = self.messages['connection_error']

        >>
```

The `update_balance` function is the important function that must eventually set the `self.last_balance` variable to a real scraped data or, in case of having an error, to an appropriate service message.

Once the provider module has been created, the `ProviderName` reference should also be added to the [JSON schema file](#json-schema-file) at the path `. > properties > identifiers > properties`, i.e.:

```yaml
...
properties:
  identifiers:
    type: object
    properties:
      ...
      ProviderName:
        $ref: '#/$defs/identifier_list'
      ...
    required:
    ...
      - ProviderName
    ...
...
```

Finally, it's possible to add the provider's identifier configuration to a [configuration file](#configuration-file) and run the exporter to scrape the data.