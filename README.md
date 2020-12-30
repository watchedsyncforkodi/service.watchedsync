# Watched Status Sync Add-on for Kodi

### Table of Contents
* [What is it?](#what-is-it)
* [What does this add-on do?](#what-does-this-add-on-do)
* [How much does it cost?](#how-much-does-it-cost)
* [Installation](#installation)
* [Need help?](#need-help)
* [Thanks to...](#thanks-to)

### What is it?
This is a service add-on for Kodi that enables real-time  synchronisation of the "watched" status between multiple kodi devices.

The "watched" status is the record Kodi makes in its internal database whether a Movie or TV episode has been watched or is partially the way through (known as a Resume point)

Unlike other solutions, this add-on:
* does not require a separate mysql/mariadb service to be installed or managed
* does not require kodi devices to be powered on 24/7 (It will remember changes to the video library for up to 14 days)
* does not need any manual synchronisation or triggering through library updates

### What does this add-on do?
* Synchronises the watched statuses of your TV episodes and Movies in the background
* Allows you to stop play back in one room and seamlessly continue watching the Movie or TV episode in another
* Refreshes the home screen in Kodi to simplify play back of in-progress Movies or TV episodes (if supported by your Kodi skin)
* *Add your feature requests to* [Issues](https://github.com/watchedsyncforkodi/service.watchedsync/issues)

### How much does it cost?
**Free** (during testing)

This add-on uses a cloud based system to provide the service. The benefit of using a cloud based service is to provide higher availability and remove the dependency on any other software or hardware running 24/7 around the home.

However, if this proves to be popular a small annual subscription may be needed to sustainably run this service.

For now assume this will remain free until further notice.

### Installation
1. Download the zip file below and save to the home folder on each kodi device:

	* [Download version for Kodi v18.x (Leia)](https://raw.githubusercontent.com/watchedsyncforkodi/repository.watchedsync.addon/kodi-v18/repository.watchedsync.addon.latest.zip)

2. Install downloaded zip.

	1. Go to *Settings* > *Add-ons* > *Install from zip file* 
	
        **Note**: If this is the first time you have installed an add-on from a zip file, Kodi will pop up a window to ask whether you will allow installation from unknown sources. This must be enabled to continue.

	2. Select *"Home folder"* > Scroll down and select *repository.watchedsync.addon.latest.zip*

	3. Still in the Add-ons menu - Go to *Install from repository* > *Watched Status Sync Add-on (Kodi vXX.X) Repository* > *Services* > *Watched Status Sync* > Install

	4. Select *OK* to install additional add-ons
	
	5. Once installed, around 30 seconds later, it pop up a window instructing you to email the registration code. **Take note of both the email address and the registration code**. The registration code will have 8 letters in the format XXXX-XXXX.

3. To complete registration, send an email to the email address noted with the registration code(s) from **all your kodi devices you want to sync.**
   
4. You will receive an email confirming registration has been completed. Please be patient, this is currently a manual process.
   
5. After receiving the confirmation email the last step is to reboot/restart all the kodi devices.
   
6. Enjoy!

### Need help?

* Search the [Issues](https://github.com/watchedsyncforkodi/service.watchedsync/issues) to see if your problem has already been reported. If not, create a new issue and provide a debug logfile. The simplest way to provide a debug log is to follow the instructions found at [Kodi Logfile Uploader Add-on](https://kodi.wiki/view/Log_file/Easy) and add the returned URL to the issue text.

### Thanks to
* Team Kodi for [Kodi](https://kodi.tv/) and the support from everyone provided in the [forums](https://forum.kodi.tv/).
* Other open-sourced add-ons that have helped guide the initial structure of this add-on.

