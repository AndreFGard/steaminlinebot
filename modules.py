import json

class cachev0:
    def __init__(self, jsonFileName: str):
        self.storage = {}
        self.changesToWrite = False
        if jsonFileName != "":
            with open(jsonFileName, "r") as f:
                self.storage = json.load(f)
        else:
            self.storage = dict()
        