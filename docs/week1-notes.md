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

## Day 2 - 3-service app (api + worker + redis)

App: api (Flask, 2 replicas, Service :80 -> :8000), worker (1 replica, no Service), redis (1 replica, Service :6379). Namespace app.
Images built locally, tagged 0.1.0, loaded with kind load (no registry).
Pod IPs: lab-worker 10.244.2.x, lab-worker2 10.244.1.x. Worker and redis landed on different nodes, so queue traffic crosses nodes.

Break: set worker image to lab/worker:0.2.0 (never loaded).
- New pod ErrImagePull/ImagePullBackOff: node expanded it to docker.io/lab/worker:0.2.0 and Docker Hub denied it.
- Old pod kept running. A rolling update does not remove the working pod until the new one is Ready.
- Fix: kubectl rollout undo. Warning: undo drifts from the last kubectl apply, so re-apply from Git afterwards.

Real bug found: worker restarted 3 times in 6 minutes.
- Traceback: redis.exceptions.TimeoutError during blpop.
- Cause: requirements said redis>=5.0, build pulled redis-py 8.1.0, whose default socket_timeout is 5s, equal to blpop timeout=5. Empty queue = client times out at the same moment.
- Fix: socket_timeout=30, retry on ConnectionError/TimeoutError, pin redis==8.1.0, new tag 0.1.1, applied from k8s/worker.yaml.
- Verified: 0 restarts after 45s idle, processed 20 -> 25.

Lessons: never deploy a tag that is not in the cluster or a registry; unpinned dependencies change behavior between builds; new code = new tag; fix via Git, not via kubectl edits.

## Day 3 - Gateway API (Envoy Gateway 1.9.3)

Install: cluster/install-envoy-gateway.sh (Helm chart also installs Gateway API CRDs).
Resources (k8s/gateway.yaml): EnvoyProxy (NodePort 30080) -> GatewayClass eg -> Gateway web (app, :80) -> HTTPRoute api (/ -> Service api:80).
Result: localhost:8080 -> api, 20 requests split 9/11 across both api pods.

Real bug: curl localhost:8080 hung.
- Inside lab-control-plane, localhost:30080 worked; from VM and Mac it hung.
- Cause: Envoy Service externalTrafficPolicy=Local (Envoy Gateway default). Envoy pod on lab-worker; host port 8080 maps to lab-control-plane, which has no Envoy pod, so external traffic was dropped. Node-local traffic is exempt, which made the in-node test misleading.
- Fix: externalTrafficPolicy: Cluster in EnvoyProxy. Trade-off: client source IP is lost (SNAT on the extra hop).
- Method: test hop by hop (Mac -> Colima ssh forwarder -> VM -> Docker -> node:30080 -> Envoy -> pods).

Packet path, api (10.244.1.3, lab-worker2) -> redis (10.244.2.9, lab-worker):
1. DNS: "redis" + search app.svc.cluster.local (ndots:5) -> CoreDNS 10.96.0.10 -> ClusterIP 10.96.29.57.
2. Packet 10.244.1.3 -> 10.96.29.57:6379 leaves pod veth into lab-worker2.
3. iptables nat on lab-worker2 (rules written by kube-proxy): KUBE-SERVICES -> KUBE-SVC-C7VB... -> KUBE-SEP-LBAK... DNAT to 10.244.2.9:6379. The kernel rewrites the destination, not the kube-proxy process.
4. Route 10.244.2.0/24 via 172.18.0.4 (kindnet, no encapsulation) -> lab-worker -> redis pod veth. Source IP preserved.
5. Reply: conntrack on lab-worker2 reverses the DNAT; api sees the reply from 10.96.29.57.
Contrast: Envoy -> api goes to pod IPs from EndpointSlices directly, no ClusterIP DNAT.

Break: HTTPRoute backendRef -> nonexistent Service "apii".
- curl 500; route status Accepted=True, ResolvedRefs=False BackendNotFound.
- Fix: kubectl apply -f k8s/gateway.yaml (Git as source of truth) -> 200.
