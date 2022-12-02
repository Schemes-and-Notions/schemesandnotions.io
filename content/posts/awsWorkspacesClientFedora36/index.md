---
title: "Building AWS client for Fedora 36"
date: 2022-12-01T23:46:00Z
draft: false
toc: false
description: How to get the AWS Workspaces Client working on Fedora 36
cover: img/cover.png
useRelativeCover: True
tags:
  - aws
  - vdi
  - workspaces
  - fedora
  - fedora 36
  - rpm
---

## **READ ME FIRST**
There is a [flatpak on flathub](https://flathub.org/apps/details/com.amazon.Workspaces).  At the time of writing this post, the version on flathub (4.3.0.1766) was behind what people were getting for Ubuntu (4.4.0.1808-2).  Additionally, it looks like that [flatpak](https://flathub.org/apps/details/com.amazon.Workspaces) is **not** maintained by AWS.  From the FlatHub page:

> NOTE: This wrapper is not verified by, affiliated with, or supported by Amazon.com, Inc

If software supply chain is important to you, this may or may not be the right choice based on your personal (or organizational) security posture.

Risk of maintaining your own package vs. depending on somebody else to do so (with all that that decision encompasses).  The rest of this post will walk you through building your own RPM and using it.

## Problem
I need to use AWS Workspaces for work.  I run Fedora at home.  AWS only releases Ubuntu packages for their Workspaces Client.  The AWS Workstation web client doesn't work if your workspace VM is linux based.

## Assumptions
- You're running Fedora 36 and have root access.
- You have an AWS workspace you want to connect to.

## Disclaimer
This is basically [a roll up of some collaboration on Reddit](https://www.reddit.com/r/aws/comments/e28fdh/the_workspaces_client_is_now_available_for_linux/).  With most of the credit going to [pgn674](https://www.reddit.com/user/pgn674/) and [Northern-Gannet-00](https://www.reddit.com/user/Northern-Gannet-00/).  All credit goes to those in the reddit thread.  

Additionally, This works for me, today, at the time of writing (see article date/time stamp).  It may not work for you in the future, but hopefully offers some breadcrumbs.

## Overview
Generally the process is going to be:
1. Download the `.deb`
2. Use `alien` to convert the `.deb` to a `.rpm`
3. Edit the `.rpm` removing some dependencies/folder specifications using `rpmrebuild`
4. Install the resultant RPM
5. Symlink a library (yuck)

## Install some dependencies
You'll need some tools, lets install them:
```bash
sudo dnf -y install rpmrebuild alien
```

## Download the deb
You can download the deb directly from:

```
https://d3nt0h4h6pmmc4.cloudfront.net/workspacesclient_focal_amd64.deb
```

Note, that this link may change over time, it can be found at the bottom of the [linux install page](https://clients.amazonworkspaces.com/linux-install.html) for AWS Workspaces under the section:

> If you need to download and install the Amazon WorkSpaces Client directly, you can find the download here [...]

## Convert the `deb` to an `rpm`
This ones pretty simple:

```bash
sudo alien --to-rpm workspacesclient_focal_amd64.deb
```

The output should be an RPM in the same directory:

```
workspacesclient-4.4.0.1808-2.x86_64.rpm
```

## Tweak the rpmspec
We have to do a couple of things to get this compatible for Fedora systems.  Run the following command, and it will drop you into your default editor with a generated RPM spec you can edit:

```bash
rpmrebuild --package --edit-spec workspacesclient-*.x86_64.rpm
```

Once the editor opens, remove the following lines:

```diff
- Requires:      liblttng-ust.so.0()(64bit)
```
User [Northern-Gannet-00 on reddit](https://www.reddit.com/r/aws/comments/e28fdh/comment/io2jzzo/?utm_source=reddit&utm_medium=web2x&context=3) determined that this library is not needed as it was just a trace library and is only used for debugging.


Right above it, edit the following line:
```diff
- Requires:      libhiredis.so.0.14()(64bit)
+ Requires:      libhiredis.so.1.0.0()(64bit)
```
This allows you to use the dependency that Fedora 36 (at the time of writing) ships with: hiredis 1.0.0.  We'll have to do a symlink after install, but *should* work for now. Also, see [warnings at the end of this post](#warnings)


As Northern-Gannet-00 also pointed out, Fedora and AWS disagree on the permissions for `/usr/lib`, so remove the following line:
```diff
- %dir %attr(0755, root, root) "/usr/lib"
```

Once those changes are made, you can save and quit your editor.  You'll be prompted if you want to continue (defaults to 'no'):

```bash
$ rpmrebuild --package --edit-spec workspacesclient-*.x86_64.rpm
(GenRpmQf) remove tag line ENHANCESFLAGS
(GenRpmQf) remove tag line ENHANCESNAME
(GenRpmQf) remove tag line ENHANCESVERSION
(GenRpmQf) remove tag line SUGGESTSFLAGS
(GenRpmQf) remove tag line SUGGESTSNAME
(GenRpmQf) remove tag line SUGGESTSVERSION
Do you want to continue ? (y/N) y
```

You'll see some errors on the screen, they shouldn't be anything to worry about.

Finally, you'll be given an output dir:

```
result: /home/mike/rpmbuild/RPMS/x86_64/workspacesclient-4.4.0.1808-2.x86_64.rpm
```

## Install the rpm
Install the rpm from the path it got dropped in:
```bash
# adjust path for your username
sudo dnf -y install /home/mike/rpmbuild/RPMS/x86_64/workspacesclient-4.4.0.1808-2.x86_64.rpm
```

## Symlink a library and some warnings
So, because of a slight mis-match of the library versions, we need a symlink of what the workspaces client is looking for to the one we installed.

**Disclaimer** - This is dirty.  Like, I'm not too proud of this.  As I said in the reddit thread:

> Warning - Understand what you're doing here; you're strapping in a newer version (major version num change) of a seemingly core library where APIs may have changed. Very well might break something. Caveat Emptor. Side effects may include Death, Disconnected Sessions, Loss of appetite.


By reading further, you understand what you're doing.  Create the symlink:

```bash
cd /usr/lib64
ln -s libhiredis.so.1.0.0 libhiredis.so.0.14
```

## Success!
Now, like any natively installed GUI app, you should be able to launch the Workspaces Client and connect to your VDI!

{{< figure src=img/workspaces_gnome_icon.png alt="" position="center" style="border-radius: 8px;" caption="AWS Workspaces Gnome Icon" captionPosition="left" >}}

## Troubleshooting
### Unable to connect
Assuming theres no other networking issues you would typically troubleshoot with accessing your workspace, this can arise if theres issues with `libhiredis`.  In my case, its because I was missing a symlink, but it could be version compatibility issues, etc.


{{< figure src=img/unable-to-connect.png alt="" position="center" style="border-radius: 8px;" caption="Unable to connect error" captionPosition="left" >}}


## References
[Reddit Post](https://www.reddit.com/r/aws/comments/e28fdh/the_workspaces_client_is_now_available_for_linux/)


#### Legal
All product and company names are trademarks™ or registered® trademarks of their respective holders. Use of them does not imply any affiliation with or endorsement by them. 