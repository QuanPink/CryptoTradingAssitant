import pandas as pd

from src.models import AccumulationZone


class EntryBuilder:

    @staticmethod
    def build_trade_plan(df: pd.DataFrame, zone: AccumulationZone, bias: str,
                         buffer_pct: float = 0.005, r_values: list = [2, 3, 4]):
        price = df["close"].iloc[-1]

        if price < zone.support or price > zone.resistance:
            return None

        if bias == "LONG":
            entry = zone.support + (zone.resistance - zone.support) * 0.35
            sl = zone.support * (1 - buffer_pct)
            direction = 1
        else:
            entry = zone.support + (zone.resistance - zone.support) * 0.65
            sl = zone.resistance * (1 + buffer_pct)
            direction = -1

        R = abs(entry - sl)

        return {
            "entry": entry,
            "stop_loss": sl,
            **{f"take_profit_{i + 1}": entry + direction * r_values[i] * R
               for i in range(len(r_values))},
            "current_price": price,
            "risk_amount": R,
            "zone_range": zone.resistance - zone.support
        }
