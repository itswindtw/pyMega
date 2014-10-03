import os
import megadb.settings as settings

settings.RELATIONS_PATH = os.path.join(os.path.dirname(__file__), settings.RELATIONS_PATH)
