---
title: "Troubleshooting k3s/containerd pods with nsenter"
date: 2022-07-11T09:00:00Z
draft: false
toc: false
description: Troubleshooting your k3s pods when the image doesn't have the right tools.
cover: cover.jpg
useRelativeCover: True
tags:
  - k3s
  - containerd
  - k8s
  - nsenter
---

## Problem
You were troubleshooting a pod the other daaaaaaayyyy.....

```
[mike@einsteinium $] k exec -it it-inventree-cache-6975b6445f-h5m5q -- bash
root@it-inventree-cache-6975b6445f-h5m5q:/data# ping
bash: ping: command not found
root@it-inventree-cache-6975b6445f-h5m5q:/data# nc
bash: nc: command not found
root@it-inventree-cache-6975b6445f-h5m5q:/data# ss -alnp
bash: ss: command not found
root@it-inventree-cache-6975b6445f-h5m5q:/data# netstat
bash: netstat: command not found
root@it-inventree-cache-6975b6445f-h5m5q:/data# f*%!
bash: f*%!: command not found

```

## Solution
`nsenter` to the rescue!  `nsenter` allows you to run commands from the namespace of the pod (like its being run on the pod) but while having access to all of the host binaries.

Once you get the PID of the container process, you're good, but the journey there is a little different for `containerd` than it is for `docker`.

### Getting the container PID on k3s
K3s runs an embeded copy of containerd under the hood, and you need to use that to access it.


Get the node that the pod is running on:

```bash
$ kubectl get pods -o wide                                                                  
NAME                                  READY   STATUS    RESTARTS   AGE   IP            NODE                  NOMINATED NODE   READINESS GATES
it-inventree-cache-6975b6445f-h5m5q   1/1     Running   0          23m   10.42.5.125   k05.svr.zeroent.net   <none>           <none>
it-inventree-db-0                     1/1     Running   0          23m   10.42.5.121   k05.svr.zeroent.net   <none>           <none>
it-inventree-proxy-87d7cf4c8-htbf5    1/1     Running   0          23m   10.42.5.123   k05.svr.zeroent.net   <none>           <none>
it-inventree-server-0                 1/1     Running   0          23m   10.42.5.122   k05.svr.zeroent.net   <none>           <none>
it-inventree-worker-9b474c5cc-5swnh   1/1     Running   3          23m   10.42.5.124   k05.svr.zeroent.net   <none>           <none>
```

SSH to that host, become root:

```bash
$ ssh k05.svr.zeroent.net
$ sudo -i
```

List the pods, get the container ID:

```
# we have to CD to /usr/local/bin because its not in roots path on CentOS
[root@k05 ~]$ cd /usr/local/bin
[root@k05 bin]# ./crictl ps
CONTAINER           IMAGE               CREATED             STATE               NAME                  ATTEMPT             POD ID
e22c931194c31       dbee21c37acc0       21 minutes ago      Running             it-inventree-server   0                   5d4477f684d7c
beade35c36e05       dbee21c37acc0       24 minutes ago      Running             inventree-worker      3                   e9a77ef5e08ed
99c8b8ef7226a       2e50d70ba706e       25 minutes ago      Running             it-inventree-cache    0                   4ea4be557b65b
31d2bc596282e       b3c5c59017fbb       26 minutes ago      Running             it-inventree-proxy    0                   33446c3487753
38b6295f3e7b8       3f0adc9c36207       26 minutes ago      Running             it-inventree-db       0                   8b3918cbfd2c4
```

We care about the `container` ID.  So if we're trying to work on the `it-inventree-cache` pod, we want `99c8b8ef7226a`.

Get the PID of the pod:
```
[root@k05 bin]# ./crictl inspect --output go-template --template '{{.info.pid}}' 99c8b8ef7226a
29107
```

### Time for some `nsenter`
Finally, use that in `nsenter` to run any command you want (as long as its on the host)!

Syntax: `nsenter -t <pid of container> -n <command and args>`

```
[root@k05 bin]# nsenter -t 29107 -n ping google.com
PING google.com (142.250.176.206) 56(84) bytes of data.
64 bytes from lga34s37-in-f14.1e100.net (142.250.176.206): icmp_seq=1 ttl=117 time=8.22 ms

[root@k05 bin]# nsenter -t 29107 -n nc -zv 10.43.191.215 80     # ip of a kubernetes service fronting a nginx container
Connection to 10.43.191.215 80 port [tcp/http] succeeded!

[root@k05 bin]# nsenter -t 29107 -n ip route
default via 10.42.5.1 dev eth0 
10.42.0.0/16 via 10.42.5.1 dev eth0 
10.42.5.0/24 dev eth0 proto kernel scope link src 10.42.5.125 

```



Note that some things wont work like you expect:
```
[root@k05 bin]# nsenter -t 29107 -n dig it-inventree-proxy.inventree.svc.cluster.local

; <<>> DiG 9.11.4-P2-RedHat-9.11.4-26.P2.el7_9.7 <<>> it-inventree-proxy.inventree.svc.cluster.local
;; global options: +cmd
;; Got answer:
;; WARNING: .local is reserved for Multicast DNS
;; You are currently testing what happens when an mDNS query is leaked to DNS
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 16714
```
Without specifying a server for DIG, its going to use your `/etc/resolv.conf` from the host system.  You'll have to specify the server you want to hit (from `/etc/resolv.conf` inside the container):
```
[root@k05 bin]# nsenter -t 29107 -n dig +short @10.43.0.10 it-inventree-proxy.inventree.svc.cluster.local
10.43.191.215
```
And thats all there is to it!  See the [sources](#sources) section for details on other things you can do (like `tcpdump`).

## Sources
- [Good RedHat blog post about using `nsenter`](https://www.redhat.com/sysadmin/container-namespaces-nsenter)
- [More nsenter goodness](https://prefetch.net/blog/2020/08/03/debugging-kubernetes-network-issues-with-nsenter-dig-and-tcpdump/)
- [Cover photo - Pixabay](https://pixabay.com/photos/doors-choices-choose-decision-1690423/)
