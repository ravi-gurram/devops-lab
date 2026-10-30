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
