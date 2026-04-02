import json

def apply_ml_prediction(price : float, volumes : float) -> str:
    # Ham gia lap du doan ML
    try:
        changes = 1 + (volumes / 10000)
        predicted_price = price * changes

        if predicted_price > price * 1.0001:
            trend = "STRONG UP"
        elif predicted_price > price:
            trend = "UP"
        else:
            trend = "DOWN"

        result = {
            "predicted_price" : round(predicted_price, 4),
            "trend" : trend,
            "confidence_score" : min(0.99, 0.5 + volume * 0.00001)
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"predicted_price" : price, "trend" : "UNKNOWN", "confidence_score" : 0.0})
        