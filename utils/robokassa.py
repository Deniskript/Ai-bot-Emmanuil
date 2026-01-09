import hashlib
from urllib.parse import urlencode
from config import ROBOKASSA_LOGIN, ROBOKASSA_PASS1, ROBOKASSA_PASS2, ROBOKASSA_TEST_MODE


def generate_payment_link(
    order_id: int,
    amount: float,
    description: str,
    user_id: int,
    payment_type: str  # "subscription" или "tokens"
) -> str:
    """
    Генерация ссылки на оплату Робокасса
    
    payment_type: "subscription:mini", "subscription:standard", "tokens:100k", "tokens:200k"
    """
    
    # Формируем подпись
    # SignatureValue = MD5(MerchantLogin:OutSum:InvId:Password1:Shp_type:Shp_user)
    
    inv_id = order_id
    out_sum = f"{amount:.2f}"
    
    # Дополнительные параметры (Shp_)
    shp_type = payment_type
    shp_user = str(user_id)
    
    # Подпись
    signature_str = f"{ROBOKASSA_LOGIN}:{out_sum}:{inv_id}:{ROBOKASSA_PASS1}:Shp_type={shp_type}:Shp_user={shp_user}"
    signature = hashlib.md5(signature_str.encode()).hexdigest()
    
    # Базовый URL
    if ROBOKASSA_TEST_MODE:
        base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
    else:
        base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
    
    # Параметры
    params = {
        "MerchantLogin": ROBOKASSA_LOGIN,
        "OutSum": out_sum,
        "InvId": inv_id,
        "Description": description,
        "SignatureValue": signature,
        "Shp_type": shp_type,
        "Shp_user": shp_user,
        "Culture": "ru"
    }
    
    if ROBOKASSA_TEST_MODE:
        params["IsTest"] = 1
    
    return f"{base_url}?{urlencode(params)}"


def verify_result_signature(out_sum: str, inv_id: str, shp_type: str, shp_user: str, signature: str) -> bool:
    """
    Проверка подписи от Робокассы (ResultURL)
    SignatureValue = MD5(OutSum:InvId:Password2:Shp_type:Shp_user)
    """
    expected_str = f"{out_sum}:{inv_id}:{ROBOKASSA_PASS2}:Shp_type={shp_type}:Shp_user={shp_user}"
    expected_signature = hashlib.md5(expected_str.encode()).hexdigest().upper()
    
    return signature.upper() == expected_signature


def verify_success_signature(out_sum: str, inv_id: str, shp_type: str, shp_user: str, signature: str) -> bool:
    """
    Проверка подписи от Робокассы (SuccessURL)
    SignatureValue = MD5(OutSum:InvId:Password1:Shp_type:Shp_user)
    """
    expected_str = f"{out_sum}:{inv_id}:{ROBOKASSA_PASS1}:Shp_type={shp_type}:Shp_user={shp_user}"
    expected_signature = hashlib.md5(expected_str.encode()).hexdigest().upper()
    
    return signature.upper() == expected_signature
