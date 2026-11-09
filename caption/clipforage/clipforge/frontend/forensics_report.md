
## Stage 2: Real-time Event Forensics

* **Stale Event Injection**: UI does not resurrect job when stale websocket event arrives: **true**
* **Duplicate/Malformed Events**: Frontend parsing try-catch safely handles invalid JSON: **true**
* **Polling Teardown**: Polling interval clears upon navigating away from dashboard: **false**
