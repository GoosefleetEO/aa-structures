from datetime import datetime, timedelta
import inspect
import logging
import json
import os


def load_testdata_entities() -> dict:
    currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
        inspect.currentframe()
    )))

    with open(
        currentdir + '/testdata/entities.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        entities = json.load(f)
    
    return entities
    

def dt_eveformat(dt: object) -> str:
    """converts a datetime to a string in eve format
    e.g. '2019-06-25T19:04:44'
    """
    dt2 = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    return dt2.isoformat()


def set_logger(logger_name: str, name: str) -> object:
    """set logger for current test module
    
    Args:
    - logger: current logger object
    - name: name of current module, e.g. __file__
    
    Returns:
    - amended logger
    """
    
    # reconfigure logger so we get logging from tested module
    f_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s'
    )
    f_handler = logging.FileHandler(
        '{}.log'.format(os.path.splitext(name)[0]),
        'w+'
    )
    f_handler.setFormatter(f_format)
    logger = logging.getLogger(logger_name)
    logger.level = logging.DEBUG
    logger.addHandler(f_handler)
    logger.propagate = False
    return logger
