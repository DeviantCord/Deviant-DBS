import os
import uuid
import glob
def writeFailedTaskJson(given_json):
    current_path = os.getcwd()
    full_path = os.path.join(current_path, "failed_jobs/")
    if not os.path.exists(full_path):
        os.mkdir(full_path)
    unique_filename = "job-" + str(uuid.uuid4()) + ".json"
    with open(str(full_path) + unique_filename, "w") as outFile:
        outFile.write(given_json)

def getFailedTaskJsonFiles():
    current_path = os.getcwd()
    failed_jobs_path = os.path.join(current_path, "failed_jobs")
    json_files = glob.glob(os.path.join(failed_jobs_path, "*.json"))
    return json_files
