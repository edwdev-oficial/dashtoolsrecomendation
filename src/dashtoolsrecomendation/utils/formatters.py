def br_num(number: float, decimals: float, use_brl: bool=False) -> str:
    """
    number: obrigatório
    decimal: obrigatório
    use_brl: opcional
    """
    
    if use_brl:
        s = f'R$ {number:,.{decimals}f}'
        return s.replace(',', '|').replace('.', ',').replace('|', '.')
    
    s = f'{number:,.{decimals}f}'
    return s.replace(',', '|').replace('.', ',').replace('|', '.')

def date_br(date):
    return date.strftime('%d/%m/%Y')