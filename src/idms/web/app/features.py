import json
import os

class Features(dict):

    def load_features(self, file_path):
        if os.path.isfile(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.clear()
                self.update(data)

FEATURES = Features()