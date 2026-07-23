import json
import pandas as pd
from pathlib import Path

def dir_base():
    return Path(__file__).resolve().parents[1] / 'data'

def read_json(name: str, tipo: str='df') -> pd.DataFrame | dict:
    DIR_BASE = dir_base()
    if tipo == 'df':
        return pd.read_json(DIR_BASE / f'{name}.json')
    else:
        with open(DIR_BASE / f'{name}.json', 'r', encoding='utf-8') as f:
            return json.load(f)

def write_json(data: pd.DataFrame | dict, name:str):
    DIR_BASE = dir_base()
    dados = None
    if isinstance(data, pd.DataFrame):
        dados = data.to_dict(orient='records')
    else:
        dados = data

    if dados:
        with open(DIR_BASE / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False, default=str)
            return 'success'
