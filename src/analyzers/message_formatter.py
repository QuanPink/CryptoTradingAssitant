"""Message formatting for Telegram notifications"""
from typing import Dict

from config.setting import settings
from src.analyzers.breakout_detector import BreakoutDetector


class MessageFormatter:
    """Format messages for different alert types"""

    @staticmethod
    def format_accumulation(symbol: str, timeframe: str, zone_info: Dict, price: float) -> str:
        """Format accumulation detection message"""
        upper = zone_info['upper']
        lower = zone_info['lower']
        width_pct = zone_info['width'] * 100
        duration = zone_info['duration_hours']
        quality = zone_info.get('quality', 'fair')

        tf_meta = settings.TIMEFRAME_METADATA[timeframe]

        # Calculate price position in zone
        if lower <= price <= upper:
            position = ((price - lower) / (upper - lower)) * 100
        else:
            position = 50

        # Quality emoji
        quality_scores = {
            'excellent': 5,
            'good': 4,
            'fair': 3
        }

        score = quality_scores.get(quality, 3)

        msg = (
            f"🚀 *PHÁT HIỆN TÍCH LUỸ*\n"
            f"━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}* | ⏱️ {tf_meta['label']}\n\n"
            f"💰 Giá: `{price:,.2f}`\n"
            f"📈 Kháng cự: `{upper:,.2f}`\n"
            f"📉 Hỗ trợ: `{lower:,.2f}`\n\n"
            f"📊 Biên độ: *{width_pct:.2f}%*\n"
            f"📍 Vị trí: *{position:.0f}%*\n"
            f"⏳ Thời gian tích luỹ: *{duration:.1f}h*\n"
            f"💪 Chất lượng: *{score}/5*\n\n"
            "\u200b"
        )
        return msg

    @staticmethod
    def format_breakout(symbol: str, timeframe: str, price: float, direction: str,
                        zone: Dict, vol_spike: bool, short_ratio: float,
                        medium_ratio: float, consensus: Dict, breakout_quality: str) -> str:
        """Format breakout message with ALL quality indicators"""

        # Build message header
        header = MessageFormatter._build_breakout_header(symbol, timeframe, price, direction, zone)

        # Build quality indicators
        quality_section = MessageFormatter._build_quality_indicators(
            vol_spike, short_ratio, medium_ratio,
            breakout_quality, consensus
        )

        # Build setup section (if volume confirmed)
        if vol_spike:
            setup_section = MessageFormatter._build_setup_section(
                price, direction, zone, breakout_quality, consensus
            )
            return header + quality_section + setup_section
        else:
            return header + quality_section + "\n⚠️ *CHỜ VOLUME XÁC NHẬN*\n"

    @staticmethod
    def format_proximity(symbol: str, timeframe: str, price: float,
                         level: float, level_type: str) -> str:
        """Format proximity alert message"""
        distance_pct = abs(price - level) / level * 100
        tf_meta = settings.TIMEFRAME_METADATA[timeframe]

        if level_type == "resistance":
            emoji = "🔴"
            title = "GIÁ GẦN KHÁNG CỰ"
            level_name = "Kháng cự"
        else:
            emoji = "🟢"
            title = "GIÁ GẦN HỖ TRỢ"
            level_name = "Hỗ trợ"

        msg = (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}*\n\n"
            f"⏱ {tf_meta['style']} ({tf_meta['label']})\n\n"
            f"💰 Giá hiện tại: `{price:.6f}`\n"
            f"🎯 {level_name}: `{level:.6f}`\n\n"
            f"📏 Khoảng cách: *{distance_pct:.2f}%*\n\n"
        )
        return msg

    # ═══════════════════════════════════════════════════════════
    # HELPER METHODS FOR BREAKOUT MESSAGE
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _build_breakout_header(symbol: str, timeframe: str, price: float,
                               direction: str, zone: Dict) -> str:
        """Build breakout message header"""
        tf_meta = settings.TIMEFRAME_METADATA[timeframe]

        emoji = "💥" if direction == "up" else "💣"
        title = "BREAK UP" if direction == "up" else "BREAK DOWN"
        level = zone['upper'] if direction == "up" else zone['lower']
        breakout_pct = abs(price - level) / level * 100

        return (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}* | ⏱️ {tf_meta['label']}\n\n"
            f"💰 Giá: `{price:,.2f}`\n"
            f"📈 Kháng cự: `{level:,.2f}`\n"
            f"📊 Breakout: *{breakout_pct:.2f}%*\n\n"
        )

    @staticmethod
    def _build_quality_indicators(vol_spike: bool, short_ratio: float,
                                  medium_ratio: float, breakout_quality: str,
                                  consensus: Dict) -> str:
        """Build quality indicators section"""
        quality_emoji_map = {'strong': '🔥', 'medium': '🟢', 'weak': '🟡'}
        quality_text_map = {'strong': 'CỰC MẠNH', 'medium': 'MẠNH', 'weak': 'YẾU'}

        # Volume line
        vol_status = "✅" if vol_spike else "⚠️"
        msg = f"📦 Volume: *x{short_ratio:.1f}* / *x{medium_ratio:.1f}* {vol_status}\n"

        # Breakout quality
        quality_emoji = quality_emoji_map.get(breakout_quality, '🟡')
        quality_text = quality_text_map.get(breakout_quality, 'MẠNH')
        msg += f"{quality_emoji} Độ mạnh: *{quality_text}*\n"

        # Consensus
        msg += MessageFormatter._format_consensus_line(consensus)

        return msg

    @staticmethod
    def _format_consensus_line(consensus: Dict) -> str:
        """Format consensus line"""
        if consensus['score'] == 0:
            return "⚠️ Đồng thuận: *KHÔNG CÓ* (0 TFs)\n"

        consensus_emoji_map = {'excellent': '🟢', 'good': '🟢', 'medium': '🟡', 'weak': '⚠️'}
        consensus_text_map = {
            'excellent': 'CỰC CAO',
            'good': 'CAO',
            'medium': 'TRUNG BÌNH',
            'weak': 'THẤP'
        }

        c_emoji = consensus_emoji_map.get(consensus['quality'], '🟡')
        c_text = consensus_text_map.get(consensus['quality'], 'TRUNG BÌNH')

        msg = f"{c_emoji} Đồng thuận: *{c_text}* ({consensus['score']}/{consensus['total']} TFs)\n"

        if consensus['aligned_tfs']:
            msg += f"   ↳ _{', '.join(consensus['aligned_tfs'])}_\n"

        return msg

    @staticmethod
    def _build_setup_section(price: float, direction: str, zone: Dict,
                             breakout_quality: str, consensus: Dict) -> str:
        """Build setup recommendation section"""
        setup = BreakoutDetector.calculate_tp_sl(price, direction, zone)

        msg = (
            f"\n━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *GỢI Ý SETUP*\n\n"
            f"📍 Entry: `{setup['entry']:,.6f}`\n"
            f"🛑 SL: `{setup['sl']:,.6f}` _(-{setup['risk_pct']:.2f}%)_\n"
            f"🎯 TP: `{setup['tp']:,.6f}` _(+{setup['reward_pct']:.2f}%)_\n"
            f"📊 R:R = *1:2*\n\n"
        )

        # Overall assessment
        msg += MessageFormatter._get_setup_assessment(breakout_quality, consensus)

        return msg

    @staticmethod
    def _get_setup_assessment(breakout_quality: str, consensus: Dict) -> str:
        """Get overall setup assessment"""
        is_strong = breakout_quality == 'strong'
        is_good_consensus = consensus['quality'] in ['excellent', 'good']
        is_medium = breakout_quality in ['strong', 'medium']

        if is_strong and is_good_consensus:
            return "🔥 *SETUP XUẤT SẮC* - Tín hiệu cực mạnh!\n"
        elif is_medium and is_good_consensus:
            return "🟢 *SETUP TỐT* - Có confirm từ TF cao\n"
        elif is_medium:
            return "🟡 *SETUP KHÁ TỐT* - Chưa confirm TF cao\n"
        else:
            return "⚠️ *SETUP YẾU* - Cân nhắc kỹ trước khi vào\n"
