---
title: "External node_exporter -> K8s cluster metrics"
date: 2022-01-05T16:00:00Z
draft: false
toc: true
description: Get metrics from your external `node_exporter` instance into your k8s based Prometheus monitoring system
cover: img/cover.png
useRelativeCover: True
tags:
  - k8s
  - prometheus
  - prometheus-operator
  - rancher-monitoring
---
## TL;DR
Use `kind: Probe` CRDs provided in the chart. See examples at the bottom.

- [CRD Spec File](https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/crds/crd-probes.yaml)

## Background
I wanted monitoring, and I had already deployed the `kube-prometheus-stack` (via the `rancher-monitoring` chart) and I wanted to leverage that for my non-k8s monitoring needs.  It seemed silly to deploy an RPM or static docker based monitoring solution when I had that shiny k3s cluster sitting there, ready to go, with something already deployed on it.  It should just be as easy as coaxing the exsisting prometheus instance to scrape other `/metrics` endpoints, right? ...right?

## Assumptions
You're deployed one of the following charts to get prometheus/prometheus-operator/grafana running in your cluster
- [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [rancher-monitoring](https://rancher.com/docs/rancher/v2.6/en/monitoring-alerting/)
  - Note: this is just using the `kube-prometheus-stack` charts under the hood, so all of the same CRDs will apply here (sorta, see [Rancher Specifics](#rancher-flavored-caveats))
- You're running `node_exporter` somewhere else, say on your desktop (or a fleet of bare metal servers doing non-k8s things).
  - For the purposes of this post, you'll see `einsteinium.lan.zeroent.net:9100` as my "external" (meaning external to the cluster) instance of `node_exporter`

## Suggestions on the internet
When you search for "prometheus operator external metrics", you come across a couple of blogs:
- https://jpweber.io/blog/monitor-external-services-with-the-prometheus-operator/
- https://devops.college/prometheus-operator-how-to-monitor-an-external-service-3cb6ac8d5acb

In both of these posts, the authors suggest to use a combination of a custom `ServiceMonitor` resource pointing to a `service` resource, pointing to a `endpoint` resource that actually references your endpoint outside the cluster.  

### The problem

Even once you get past the improperly indented yaml examples, there are some problems with this solution:

1. It requires you to reference the external instance by IP Address (no hostname)
2. You have to define (and keep in sync) 3 resources just to monitor one node

The first point being the biggest; it makes the whole setup somewhat fragile.  If you change your IP, you have to update some of the resources.  If you're doing any hostname-based proxying on the target, you're hooped.


## The "right" way to do it (another way)
One of the [comments on one of the blogs](https://medium.com/@iftachsc/although-this-is-working-this-is-some-how-misleading-because-this-is-much-harder-then-the-right-69e37e8e1f22) pointed out the "right" way to solve this problem per [the prometheus docs](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/additional-scrape-config.md).

This solution involves you manually modifying the `kind: Prometheus` resource that was deployed with the helm chart (danger) and pointing to `kind: Secret` resource where you're going to define, in traditional prometheus config format, extra jobs for Prometheus to go do.

### The problem
1. You're manually modifying the main `Prometheus` custom resource (which tells the `prometheus-operator` how to deploy/configure prometheus). The moment you run a `helm upgrade` on your installation, those changes could very well get blown away.
2. You have one secret that you have to update any time you want to add/remove an endpoint for monitoring.
   1. k8s secrets are notoriously messy to update. You basically have to keep the source of the secret and re-generate it every time, ala:
```bash
kubectl create secret generic additional-scrape-configs --from-file=prometheus-additional.yaml --dry-run=client -oyaml | kubectl apply -f - -n cattle-monitoring-system
```

## Solution: Using the `kind: Probe` CRD
So, there has to be a better way (at least, I think its a better way).  While trying to get [blackbox_exporter](https://github.com/prometheus-community/helm-charts/tree/main/charts/prometheus-blackbox-exporter) to work, I came across the `kind: Probe` CRD provided by the `prometheus-operator` chart.  All of the examples of using this CRD reference the blackbox_exporter, but after some digging, you can use it to create prometheus jobs.  At the end of the day, all of the methods described here on the page are, one way or another, just appending to the active prometheus jobs configuration section.  So if you can get a 

You'll want to create a resource that looks something like this:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: Probe
metadata:
  name: einsteinium-node-exporter-probe-1
  namespace: cattle-monitoring-system
  labels:
    release: "rancher-monitoring"
spec:
  jobName: einsteinium-node-exporter-probe-1
  interval: 10s
  prober:
    url: einsteinium.lan.zeroent.net:9100
    path: /metrics
  targets:
    staticConfig:
      relabelingConfigs:    # see "Rancher-flavored Caveats"
      - replacement: einsteinium-node-exporter-probe
        targetLabel: instance
      - replacement: einsteinium-node-exporter-probe
        targetLabel: target
      static: 
      - einsteinium.lan.zeroent.net:9100
#      labels: 
#        target: "einsteinium-node-exporter-probe"
```

When we `kubectl apply -f` this config, we see the resulting prometheus config changes:



### Notes
In the example above, I'm showing the use of `relabelingConfigs` and left in the commented-out `labels` directive.  You can use either, but don't use both. Also, be sure to read [rancher-flavored caveats](#rancher-flavored-caveats).

As far as I can tell, you need to define the hostname in both `targets.staticConfig.static[]` as well as `prober.url`.  If you don't define it in `targets.staticConfig.static[]`, then the job doesnt get created.  If you don't define `prober.url`, you cant define `prober.path` (`url` is a required key per the spec), but you need to define `prober.path` to `/metrics`, otherwise it's going to query `/probe` (see [Disadvantages](#disadvantages))

### Advantages
This has several advantages over the current recommended way of using 
1. No modifying the original deployment of `prometheus-operator`
2. One resource per monitoring target.  This allows you to easily template out the resource definition and plumb it into your automation for host provisioning:
   - New host? apply one of these resources.
   - Deleting host? delete the corresponding resource


### Disadvantages
To be clear, this is abusing the `probe` CRD.  It seems like it was intended largely for the `blackbox_exporter`:
1. All docs examples for the prober CRD reference using it for `blackbox_exporter`
   1. [CRD Spec File](https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/crds/crd-probes.yaml)
   2. [Probe CRD operator docs](https://prometheus-operator.dev/docs/operator/design/#probe)
2. Even though we're overriding the path, it still is pushing `blackbox_exporter` style arguments (see below).  Thankfully `node_exporter` just ignores them and passes back the metrics as expected.
{{< figure src=img/wireshark.png alt="" position="center" style="border-radius: 8px;" caption="Wireshark capture of incoming request" captionPosition="left" >}}
   This isnt necessarily a problem, but 
3. Because we're abusing the functionality of the `probe`, this solution could break with any update.

## Rancher-flavored Caveats
So a quick note on the example provided above.  It's opinionated to work for [the `rancher-moniotoring` version of the helm chart](https://github.com/rancher/charts/blob/release-v2.6/charts/rancher-monitoring/rancher-monitoring-crd/100.0.0%2Bup16.6.0/crd-manifest/crd-probes.yaml).

The main difference being that you declare your metric relabeling configs under [`.spec.target.staticConfig.relabelingConfigs`](https://github.com/rancher/charts/blob/release-v2.6/charts/rancher-monitoring/rancher-monitoring-crd/100.0.0%2Bup16.6.0/crd-manifest/crd-probes.yaml#L202) as opposed to current `kube-prometheus-stack` chart has you defining them under [`.spec.metricRelabelings`](https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/crds/crd-probes.yaml#L156).

This is due to a refactor in the `kind: Probe` CRD occuring between the version of `kube-prometheus` that the `rancher-monitoring` chart is using (v0.48.0) and the mainline version from upstream (`kube-prometheus`, v0.53.1).

What this all means: If you're using the upstream `kube-prometheus` chart (rather than the `rancher-monitoring` chart) and you want to use the dynamic relabeling provided by prometheus, you'll have to specify it directly under `spec` as `metricRelabelings` like so:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: Probe
metadata:
  name: einsteinium-node-exporter-probe-1
  namespace: cattle-monitoring-system
  labels:
    release: "rancher-monitoring"
spec:
  jobName: einsteinium-node-exporter-probe-1
  interval: 10s
  prober:
    url: einsteinium.lan.zeroent.net:9100
    path: /metrics
  metricRelabelings:
  - replacement: einsteinium-node-exporter-probe
    targetLabel: instance
  - replacement: einsteinium-node-exporter-probe
    targetLabel: target
  targets:
    staticConfig:
      static: 
      - einsteinium.lan.zeroent.net:9100
#      labels: 
#        target: "einsteinium-node-exporter-probe"
```

## The real right solution
Ideally, the `prometheus-operator` would provide a generic scrape config CRD, and it just so happens [theres a open GitHub issue for this](https://github.com/prometheus-operator/prometheus-operator/issues/2787).  As soon as that gets implemented, you'll have a nice, clean, k8s-native way to point at external scrape points.