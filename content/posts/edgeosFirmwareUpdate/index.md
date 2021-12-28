---
title: "Updating EdgeOS Firmware"
date: 2021-12-28T11:55:00Z
draft: false
toc: false
description: Updating storage constrained Ubiquiti devices
cover: cover.png
useRelativeCover: True
tags:
  - Ubiquiti
  - Docker
  - EdgeRouter X
---
## TL;DR
Run `add system image` but point at a `http://` url, either via Ubiquiti's download page or an internally hosted web server.

## Problem
- You have your shiny new Ubiquiti EdgeRouter X, but you need to update the firmware.  
- You want to update it via the CLI because Web UIs are for chumps.  
- You don't want to connect it to the internet because its running some horrifically old version of firmware and should be patched before it talks to the internet.  

You do what most would do:
- SCP the firmware out to the device
- run `add system image <firmware file>.tar`

Only to get the error:
```
Checking upgrade image...Done
Preparing to upgrade...Done
Copying upgrade image...Not enough disk space for root file system
Do you want to delete old version first? (Yes/No) [Yes]:   
Removing old image...Done
Still not enough disk space for root file system
Canceling upgrade
```
You delete everything you can from the disk, but still don't have enough space.  How are you supposed to do this? And why does it work from the web interface?


## Solution
As far as I can tell, when you upload the firmware package from the Web UI, it's decompressing/unpacking it as it goes; subsequently you don't need to keep 2 copies on disk. When your root partition is under 256 MB, it can make all the difference:

```
ubnt@EdgeRouter-X-5-Port:~$ df -h
Filesystem                Size      Used Available Use% Mounted on
ubi0_0                  214.9M    142.5M     67.7M  68% /root.dev
```
> `df -h` With one firmware image loaded and a copy sitting `/home/ubnt` to install

The way to do this from the CLI is reference a web URL.  If you're connected to the internet, thats easy:

```
add system image https://dl.ui.com/firmwares/edgemax/v1.10.11/ER-e50.v2.0.9-hotfix.1.5371034.tar
```

But if you're trying to do this offline/airgapped, you need to spin up your own web server to host the firmware file.  Quick way to do that with docker:

```
docker run -it --rm -v /tmp/firmwareDL:/usr/share/nginx/html -p 8080:80 nginx:latest
```

And then on your EdgeRouter:
```
add system image http://192.168.1.42:8080/ER-e50.v2.0.9-hotfix.1.5371034.tar
```

Replace `192.168.1.42` with whatever the ip address of your workstation is that your EdgeRouter will be able to hit.