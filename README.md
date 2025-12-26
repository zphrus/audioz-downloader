# audioz downloader

this is a simple desktop tool designed to make downloading from audioz through real-debrid a lot less tedious. instead of manually copying links, jumping through debrid, and also wasting your precious time on extracting the archive, this app automates the whole sequence for you.

---

## features

* **integrated search:** find what you need on audioz without leaving the app.
* **seamless debrid integration:** it automatically grabs hoster links and sends them to real-debrid for higher speed downloads.
* **auto extraction:** it can automatically unzip or unrar your files as soon as they finish downloading.
* **auto cleanup:** has an option to delete the leftover archive parts once extraction is successful to save space.
* **custom interface:** you can tweak the colors of the ui and the logs to fit your desktop setup.

---

## setup

### requirements

* **python 3.8 or higher**
* **audioz account:** you'll need your api token from their site, mainly due to bypassing captchas.
* **real-debrid account:** you'll need your api token from their site.

### installation

1. clone this folder or download the script.
2. install the necessary libraries:
`pip install -r requirements.txt`
3. launch the app:
`python3 audiozdownloader.py`

---

## configuration

head into the settings menu to get things running:

1. **audioz cookie:** you'll need to paste your session cookie from the audioz website so the app can fetch links on your behalf.
2. **api token:** paste your real-debrid api key here.
3. **download strategy:** choose "auto" if you want downloads to start immediately, or "manual" if you prefer to check the links first.
4. **appearance:** if the default look isn't for you, use the color pickers to change the accent colors and log highlights.

---

## contributing

if you run into bugs or have an idea for a feature, feel free to open an issue or submit a pull request which would be highly appreciated.
