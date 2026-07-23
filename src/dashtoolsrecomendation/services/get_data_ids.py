import pandas as pd
from dashtoolsrecomendation.database.database import (
    get_database
)

def get():
    db = get_database()
    collection = db['ccs_sorocaba_brasilia_ids']
    df = pd.DataFrame(collection.find().to_list())
    df.rename(columns={'codClie': 'Id'}, inplace=True)
    df['Id'] = df['Id'].astype(str).str.zfill(10)
    return df[['Id', 'UF', 'cliente']]

