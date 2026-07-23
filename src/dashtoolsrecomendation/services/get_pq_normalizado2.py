from dashtoolsrecomendation.services.normalization import normalizar


def get(df):
    return normalizar(df, somente_tlm=True)
