---
title: "AWS Workspaces Client for Fedora 39 (for all?)"
date: 2024-03-08T12:00:00Z
draft: false
toc: false
description: How to get the AWS Workspaces Client working on Fedora 39 (or any non-ubuntu distro)
cover: img/cover.png
useRelativeCover: True
tags:
  - aws
  - vdi
  - workspaces
  - fedora
  - fedora 39
  - rpm
---

## "Old tricks are the best tricks, eh?"  Yeah, unless they don't work.
So fast forward a year and change, and my now [well seasoned directions](posts/awsworkspacesclientfedora36/) no longer apply.  I tried re-following those directions on Fedora 39 but it was just dependency after dependency.  I figured, "There has to be a better solution".

And there was... Enter  [**DISTROBOX**](https://gitlab.com/89luca89/distrobox).

In short, this allows you to run different distributions in containers, but handles all the bind-mounting and passing through to your desktop session so it feels like a first-class experience.

## My setup
This was tested on Fedora 39, 26FEB2024 with mostly updated host, using docker rather than podman for distrobox container runtime. I'd assume that any system that supports distrobox should be able to do this, but I haven't tested, caveat emptor.

I used the Ubuntu 20.04 AWS workspaces client (2023.2.4623). This is due to the fact that my workspaces environment runs linux and AWS only supports the PCoIP protocol, not their new WSP hotness (also why using the AWS Workspaces Web client doesn't work).


## Installing Distrobox
So let's get to it!  First, you'll need to install distrobox.  As they have [good install instructions](https://distrobox.it/#installation), I won't duplicate that here in the post.  Follow for your distribution and come back here when you're done.

## Create Distrobox container

First, you're going to want to create a new distrobox container, and then promptly exit it:

```bash
distrobox create -i ubuntu:20.04 --name ubuntu2004

# this kicks off the distrobox container initialization, once its done, it will drop you into a shell into your container
distrobox enter ubuntu2004

# once the container shell is there, go ahead and exit
exit

```

## Add yourself to the sudoers
On Fedora i had to add myself to sudo group in the distrobox container manually.  From the tooling it looks like this might supposed to be automatic, but it wasn't working for me.  Fortunately, the fix was easy.  Simply run:

```bash
docker exec -it ubuntu2004 usermod -aG sudo $USER
```
You'll only have to do this once as long as you have the container.

Finally, re-enter your distrobox container, now with sudo permissions!
```bash
distrobox enter ubuntu2004 # this re-loads your group membership and drops you in a shell again
```

## Actually installing the AWS Workspaces Client

Once in distrobox, install deps missing from workspaces client package spec:
```bash
sudo apt install libcanberra-gtk-module libcanberra-gtk3-module packagekit-gtk3-module -y
```

Download the PCoIP workspaces client:
```bash
# https://clients.amazonworkspaces.com/linux-install
cd /tmp && wget https://d3nt0h4h6pmmc4.cloudfront.net/new_workspacesclient_focal_amd64.deb
```

Install it:
```bash
sudo apt install ./new_workspacesclient_focal_amd64.deb
```

And then finally, launch your client!
```bash
workspacesclient
```

If everything went successfully, you should now be able to login and use your workspaces as normal.

Note, I did try full screen and it seemed to handle my 3 external monitors (1 portrait, 2 landscape) and laptop monitor all pretty well, (even kept the "T" screen arrangement I have).  Good Luck!