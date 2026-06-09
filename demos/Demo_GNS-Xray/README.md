### VAST GNS Real-Time Image Annotation Workflow Demo

A Python/Flask application demonstrating **real-time data synchronization** and **distributed collaboration** across a **VAST Data Global Namespace (GNS)**.  

It demonstrates how shared data access and live updates work seamlessly across geographically distributed clients by mounting the same GNS-backed view on multiple systems.   

### Overview
This demo simulates a **Producer-Consumer workflow** (e.g., an X-Ray Lab generating files and a remote Radiology Technician annotating them). Two distinct web applications (Producer and Editor) run on separate VAST clusters but access the exact same dataset mounted via GNS, ensuring **real-time data consistency** and collaborative updates without manual refreshing.

### Key Technologies
* **Backend Storage:** VAST Data Global Namespace (GNS)
* **Web Framework:** Flask (Python)
* **Image Processing:** Pillow (`PIL`)
* **Real-time Updates:** Client-side polling using JavaScript.

---

### Architecture and Setup

The application is designed to run on **two separate servers** (Producer and Editor), both configured to mount the same VAST GNS view.

#### Prerequisites
* Python 3.8+
* `flask`, `Pillow` (Dependencies are installed via `virtual_env.sh`).
* The VAST GNS share must be mounted on both systems at: `/mnt/vast/gns_demo/`.

#### 1. File Structure

```text
Dataset
├── xray-11234-knees.jpg
├── xray-11243-wrist.jpg
├── xray-11256-hand.jpg
├── xray-2122140_1280.jpg
├── xray-212233-90.jpg
├── xray-21228653576-9764.jpg
├── xray-21228653576-9988-teeth.jpg
├── xray-21243689-904.jpg
├── xray-2125490-098.jpg
├── xray-2126109875-1276.jpg
├── xray-21287640-789.jpg
└── xray-2129436_1280.jpg
flask_origin
├── app.py
├── commands.txt
├── templates
│   └── index.html
└── vastmount.txt
flask_satellite
├── app.py
├── templates
│   └── index.html
└── vastmount.txt

GNS_FlaskDemo.tar.gz
```

* Dataset: Source images
* flask_origin:  For origin server
* flask_satellite: For satellite server
* GNS_FlaskDemo.tar.gz: This whole folder

#### 2. Configure Server Role (Crucial Step)

The `app.py` file is the same on each node but must be edited on each server to define its role via the `APP_ROLE` variable near the top of the file:

| Server | Role | `app.py` Setting | Functionality |
| :--- | :--- | :--- | :--- |
| **Producer** | Data Generator | `APP_ROLE = 'producer'` | View-only; hides the "Process" button. |
| **Editor** | Annotator/Consumer | `APP_ROLE = 'editor'` | Displays the "Process" button; runs the annotation logic. |


### Running the Application

Start the Flask application on **both** servers:

```bash
# On both Producer and Editor servers
source ~/vastdemo-venv/bin/activate
(vastdemo-venv) labuser@client01:~$ python app.py
```

### Demo Workflow

#### 1. Test Ingestion (Producer Action)

Open the web interface on both the Producer and Editor servers (e.g., http://<IP>:8080)
Copy a new image into the mounted origiun view on the "Producer":

```bash
$ cp test_image.jpg /mnt/vast/gns_demo/images/new_scan_1001.jpg
```

Observation: Both browser windows will automatically reload within 5 seconds, and the new image will appear.

#### 2. Test Collaboration (Editor Action)

On the Editor browser, click the "Process" button for the newly added image.  
Python annotates the image and copies it the "Processed" folder on the satellite

Observation:
The Editor's page reloads, showing Processed image
The Producer's browser automatically detects the change in the processed file count (via the GNS write) and refreshes, instantly displaying the annotated image.
 

---

#### Author/s

- **Karl Vietmeier**

#### License

This project is licensed under the Apache License - see the [LICENSE.md](LICENSE.md) file for details