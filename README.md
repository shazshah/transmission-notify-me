## Synopsis

A python script which will notify you with a Slack message when Transmission has finished downloading.

## Motivation

I was downloading OpenSUSE and Ubuntu Linux distributions using bittorrent. They were taking a while to download. Rather than sit there and wait for the download to finish I thought it would be nice if I could be notified via some message that the download has finished.

## Installation

This is just a script written in **Python3**. To 'install' it you are best running it as a **cronjob** or **launchd** (that's how i use it). The repo contains an example plist which runs the script every 20 minutes. You need to modify the location of where you have saved the python script so it knows what to run.

You also need to include information about your **Slack** account and **Transmission** details. Again, the repo contains an example file called **"example_config.secrets"**. Rename the file to **"config.secrets"** and then complete the relevant sections of the file with your details.

When the script runs it will create a small sqlite database file and a log file in the same location.

## Tests

The simplest test is to download something (e.g. a Linux Distrution) and let it successfully download (i.e it is in a state of complete or seeding).

Then, run the python script making sure you completed the config.secrets file first. If the script runs successfully you should get a Slack message.

## License

Use freely for **legal** downloads like Linux Distributions.