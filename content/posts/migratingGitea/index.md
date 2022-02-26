---
title: "Migrating Gitea from Docker to Kubernetes"
date: 2022-01-27T04:32:09Z
draft: false
toc: false
description: Going through the tumultuous job of migrating between containerization platforms.
cover: cover.png
useRelativeCover: True
tags:
  - gitea
  - k8s
  - docker
---
## Problem
I deployed Gitea initially using docker compose to just get it up and running. As things progressed on my team, we migrated most of our core services to k8s. Gitea was one of those core services.  You'd think just a simple app backup/restore, except that [Gitea has no real 'restore' functionality](https://docs.gitea.io/en-us/backup-and-restore/#restore-command-restore).

## Assumptions
I'm going to assume a couple of things for the sake of keeping this brief.
- You're migrating to/from the same version of Gitea and same database backend (in this case, I'm going to be using Postgres). I originally wasn't but doing an upgrade on your Docker installation solves this problem.
- You have successfully deployed Gitea to your k8s cluster using [their helm chart](https://gitea.com/gitea/helm-chart/)
  - you gitea pod is called `gitea-0`
  - your postgres pod is called `gitea-postgres-0`
  - you've deployed into the `gitea` namespace
- You have a Docker-based installation:
  - Your Gitea container is called `gitea` and have `/data` in the container bind-mounted to `/opt/dockervol/gitea/gitea-data` on the host*
  - Your Postgres database container is called `gitea_db` and have `/var/lib/postgresql/data` in the container bind-mounted to `/opt/dockervol/gitea/postgres` on the docker host*

> \* You can accomplish these tasks without the bind mounts. Instead of copying the tarballs/dumps directly off the docker host filesystem, you'll have to do a `docker cp` to get them out of the container first. From there, copy them to where you can work with them and k8s (specifically where you can execute `kubectl` from).

## Deploy gitea with the helm chart
I deployed the helm chart with relatively default values. I'm not going to go through the whole process here.  One thing I did do (relevant to this migration) is upgrade the `bitnami/postgres` container to a later version so I had a better chance at the database import.  In my `values.yaml` for the `helm` install:

```yaml
postgresql:
  enabled: true
  ...
  image:
    tag: 12-debian-10
  ...
```

## Database Migration
On the docker host:
```bash
# enter the container
docker exec -it gitea_db /bin/bash
```

And then, in the container
```bash
# dump the db
pg_dump gitea -U gitea > /var/lib/postgresql/data/gitea_manual_dump.sql
```

Get that dump file off of the docker host and to somewhere where you can run `kubectl` on your new cluster. 

Before we do any work with the database on k8s, we need to stop Gitea so it doesn't write while we're pulling our Peter Venkman tablecloth trick.  Scale down the `gitea` `StatefulSet`:
```bash
kubectl scale statefulset gitea --replicas 0
```

Then copy the file in to the Postgres container and then get a shell on it:
```bash
kubectl cp gitea_manual_dump.sql gitea-postgres-0:/tmp/. -n gitea
kubectl exec -it gitea-postgresql-0 -- /bin/bash
```

Once in the container, drop the current database, create a new one, and import your dump. You'll need the gitea postgres password you deployed the helm chart with.
```bash
psql template1 -c 'drop database gitea;' -U gitea
psql template1 -c 'create database gitea with owner gitea; -U gitea
exit
```

Scale your `gitea` `StatefulSet` back up to `1` to start the pod again
```bash
kubectl scale statefulset gitea --replicas 1
```

And thats it! Well, for the database. Now on to the gitea repos and associated data.

## Repo/metadata migration
So here things aren't as cut/dry.  Your best bet is to look at your docker gitea config (stored typically in `/data/gitea/conf/app.ini` in the docker install) and see whats getting referenced.

The things I found I needed to pay attention to were:

```ini
[repository]
ROOT = /data/git/repositories

[repository.local]
LOCAL_COPY_PATH = /data/gitea/tmp/local-repo

[repository.upload]
TEMP_PATH = /data/gitea/uploads

[picture]
AVATAR_UPLOAD_PATH            = /data/gitea/avatars
REPOSITORY_AVATAR_UPLOAD_PATH = /data/gitea/repo-avatars
DISABLE_GRAVATAR              = false
ENABLE_FEDERATED_AVATAR       = true

[attachment]
PATH = /data/gitea/attachments
```
For each of these sections, look at the paths and see if theres any data in them (say, for example, `/data/gitea/avatars`). Make note of those dirs (and their settings), you may need to add some configuration stanzas to your k8s config.

In general, just tar up the whole `/data` dir (or `/opt/dockervol/gitea/gitea-data` on your docker host), and get it to a host where you can kubectl with:
```bash
tar cvfz gitea-data.tgz /opt/dockervol/gitea/gitea-data
```

Copy it into the container (just like we did with Postgres), and get your self a shell on that pod in k8s
```bash
kubectl cp gitea-data.tgz gitea-0:/tmp/. -n gitea
kubectl exec -it gitea-0 -- /bin/bash
```

Once in the pod, extract that directory and start migrating data over.  In my installation, I was going from Gitea 1.14.x in docker to 1.15.x in k8s. For some reason, in the docker container, my folder structure looks like this:
```
# tree -L 2
/data
├── git
│   ├── lfs
│   └── repositories
├── gitea
│   ├── attachments
│   ├── avatars
│   ├── conf
│   ├── indexers
│   ├── jwt
│   ├── log
│   ├── queues
│   ├── repo-archive
│   ├── repo-avatars
│   └── sessions
...
```

And in the k8s `gitea-0` pod, it looked like this:
```
# tree /data -L 2
/data
├── attachments
├── avatars
├── git
│   └── gitea-repositories
├── gitea
│   ├── conf
│   └── log
├── indexers
│   └── issues.bleve
├── jwt
│   └── private.pem
├── lfs
├── lost+found
├── queues
│   └── common
├── repo-archive
├── repo-avatars
...
```

Why the moved some of the directories, who knows.  The main point is that if a section (say, for example `[repositories]`) was pointing at `/data/git/repositories` in my docker install, I copy that folder out of the data tarball currently in `/tmp` in the container and put it wherever the gitea installation on k8s expects it. In my case the k8s instance was expecting it in `/data/git/gitea-repositories`).  

Additionally, you may need to add stanzas to your k8s config.  I had to add my `[pictures]` stanza so that the `Organization` and `Repository` avatars werent missing.  These are stored on the filesystem whereas the user ones are stored in the database (as far as I can tell):

```ini
[picture]
AVATAR_UPLOAD_PATH            = /data/gitea/avatars
DISABLE_GRAVATAR              = false
ENABLE_FEDERATED_AVATAR       = true
```

Once you think you've migrated all your changes, exit the pod and delete it so it gets re-created by the `StatefulSet`:
```bash
kubectl delete pod gitea-0 -n gitea
```

Once the pod comes back up, navigate to the website and poke around, try to create issues, push to the repo, etc.  If you don't get any `500` errors, you're good to go!

Additional things I did for good measure (though not sure if I needed them):
- ran the re-generate hooks script specified at the end of the backup/restore docs on my k8s install: `./gitea admin regenerate hooks`
- ensure everything under my repository directory (`/data/git/gitea-repositories` on the `gitea-0` container) was owned by `git` (user and group)

## Summary
It's not an immediately obvious transition, but well worth the time.  If you have any questions, or find any issues with this tutorial, [reach out!](mike@schemesandnotions.io)


## references
[Gitea backup/"restore"](https://docs.gitea.io/en-us/backup-and-restore/)  
[dump and recreate psql database](https://www.netguru.com/blog/how-to-dump-and-restore-postgresql-database)  
[reddit users trying to migrate](https://www.reddit.com/r/selfhosted/comments/b0zaa8/gitea_migrate_from_manual_installation_to_docker/)  

#### Legal
All product and company names are trademarks™ or registered® trademarks of their respective holders. Use of them does not imply any affiliation with or endorsement by them. 