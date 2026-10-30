# Week 1 notes

## Day 1 - cluster + DNS break/fix

Cluster: kind, 1 control-plane + 2 workers, Kubernetes v1.37.0, CNI kindnet.

DNS path: pod -> kube-dns Service (10.96.0.10) -> kube-proxy rule -> CoreDNS pod (10.244.x.x).

Break: scaled coredns to 0.
- Pods: none.
- EndpointSlice kube-dns: ENDPOINTS <unset>. Service IP still exists.
- Client: "write to 10.96.0.10: Connection refused". kube-proxy rejects traffic to a Service with no endpoints.

Fix: scaled coredns to 2.
- EndpointSlice repopulated (10.244.1.2, 10.244.2.5).
- First retest still refused: kube-proxy had not yet replaced the reject rule. Second retest resolved.

Lesson: when a Service fails, check endpoints first. Recovery order is pods Ready -> EndpointSlice -> kube-proxy rules.
