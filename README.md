# Watched Status Sync Add-on for Kodi

### Table of Contents
* [What is it?](#what-is-it)
* [What does this add-on do?](#what-does-this-add-on-do)
* [How much does it cost?](#how-much-does-it-cost)
* [Installation](#installation)
* [Things to note](#things-to-note)
* [Need help?](#need-help)
* [Thanks to...](#thanks-to)

### What is it?
This is a service add-on for Kodi that enables real-time  synchronisation of the "watched" status between multiple Kodi devices.

The "watched" status is the record Kodi makes in its internal database whether a Movie or TV episode has been watched or is partially the way through (known as a "resume point")

Unlike other solutions, this add-on:
* does not require a separate mysql/mariadb service to be installed and managed
* does not require kodi devices to be powered on 24/7 (It will remember changes to the video library for up to 14 days)
* does not need any manual synchronisation or triggering through library updates

### What does this add-on do?
* Synchronises the watched statuses of your TV episodes and Movies in the background
* Allows you to stop playback in one room and seamlessly continue watching the Movie or TV episode in another
* Refreshes the home screen in Kodi to simplify play back of in-progress Movies or TV episodes (if supported by your Kodi skin)
* Allows synchronisation of watched statuses between different major Kodi versions (e.g. Kodi v19 & v20) - useful when testing new versions of Kodi
* *Add your feature requests to* [Issues](https://github.com/watchedsyncforkodi/service.watchedsync/issues)

### How much does it cost?
**Free**

This add-on uses a cloud based system to provide the service. This provides higher availability and removes the dependency on any other software or hardware running 24/7 in the home.

However, if this add-on becomes very popular a small annual subscription may be needed to sustainably run this service.

For now assume this will remain free until further notice.

### Installation
1. Download the zip file below and save to the home folder on each Kodi device:

    * [Download version for Kodi v18.x (Leia)](https://raw.githubusercontent.com/watchedsyncforkodi/repository.watchedsync.addon/kodi-v18/repository.watchedsync.addon.latest.zip)
    * [Download version for Kodi v19.x (Matrix)](https://raw.githubusercontent.com/watchedsyncforkodi/repository.watchedsync.addon/kodi-v19/repository.watchedsync.addon.latest.zip)
    * [Download version for Kodi v20.x (Nexus)](https://raw.githubusercontent.com/watchedsyncforkodi/repository.watchedsync.addon/kodi-v19/repository.watchedsync.addon.latest.zip)
    * [Download version for Kodi v21.x (Omega)](https://raw.githubusercontent.com/watchedsyncforkodi/repository.watchedsync.addon/kodi-v19/repository.watchedsync.addon.latest.zip)

2. Install downloaded zip.

    1. Go to *Settings* > *Add-ons* > *Install from zip file* 
	
        **Note**: If this is the first time you have installed an add-on from a zip file, Kodi will pop up a window to ask whether you will allow installation from unknown sources. This must be enabled to continue.

    2. Select *"Home folder"* > Scroll down and select *repository.watchedsync.addon.latest.zip*

    3. Still in the Add-ons menu - Go to *Install from repository* > *Watched Status Sync Add-on (Kodi vXX.X) Repository* > *Services* > *Watched Status Sync* > Install

    4. Select *OK* to install additional add-ons
	
    5. Once installed, around 30 seconds later, it pop up a window instructing you to email the registration code. **Take note of both the email address and the registration code**. The registration code will have 8 letters in the format XXXX-XXXX.

3. To complete registration, send one email to the email address noted with the registration code(s) **for all your Kodi devices you want to sync.**
   
4. You will receive an email confirming registration has been completed. Please be patient, this is currently a manual process.
   
5. After receiving the confirmation email the last step is to reboot/restart all the Kodi devices.
   
6. **That's it!**

7. (Optional) This add-on is designed to work quietly in the background with little visual feedback, **To test it is working**, highlight a movie on the home screen and bring up the Context Menu in Kodi (you can normally press 'c' on the keyboard to bring up the menu). Select "Mark as watched". Within a few seconds the other Kodi devices will mark the same movie as watched! On another Kodi device bring up the Context Menu again for the same movie, this time selecting "Mark as unwatched". Within a few seconds the other Kodi devices will mark the movie as unwatched.   

### Things to note

* The add-on requires use of the [Kodi video library](https://kodi.wiki/view/HOW-TO:Create_Video_Library). File/direct playback will not synchronise.
* The add-on will pause syncing while Kodi is playing a video or when the video library is being updated.
* The add-on commences sync around 45 secs after Kodi boots. If you haven't started Kodi for a while then leave it idle for a few minutes to work through and sync the changes.
* This service can sync up to six Kodi devices.
* Each Kodi device should use the same metadata information provider.
* Not essential but all functionality is enabled if each Kodi device has the same path to the shared media storage.
* You can check the add-on status by going into the settings screen.

### Need help?

* Search the [Issues](https://github.com/watchedsyncforkodi/service.watchedsync/issues) to see if your problem has already been reported. If not, create a new issue and provide a debug logfile. The simplest way to provide a debug log is to follow the instructions found at [Kodi Logfile Uploader Add-on](https://kodi.wiki/view/Log_file/Easy) and add the returned URL to the issue text.

### Thanks to
* Team Kodi for [Kodi](https://kodi.tv/) and the support from everyone provided in the [forums](https://forum.kodi.tv/).
* Other open-sourced add-ons that have helped guide the initial structure of this add-on.
