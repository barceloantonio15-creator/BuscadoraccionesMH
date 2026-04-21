"""
Estrategia GROW - Growth Momentum Near All-Time Highs
Basada en CANSLIM + Green Line Breakout
Versión mejorada con soporte para API web, progreso en tiempo real y caché
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
import warnings
import logging
import time

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class GrowthStrategyScanner:
    """
    Scanner para estrategia de crecimiento (GROW Method)
    Busca acciones cerca de máximos históricos con momentum
    """

    def __init__(self):
        self.universe = self._get_stock_universe()
        self.results = []
        self.scan_status = {
            'running': False,
            'progress': 0,
            'total': 0,
            'current_ticker': '',
            'start_time': None,
            'end_time': None,
            'error': None,
        }

    def _get_stock_universe(self) -> List[str]:
        sp500_tickers = [
            'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'TSLA', 'NVDA', 'BRK-B',
            'UNH', 'JPM', 'JNJ', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'LLY',
            'ABBV', 'PFE', 'BAC', 'KO', 'AVGO', 'PEP', 'MRK', 'COST', 'TMO',
            'DIS', 'ABT', 'CSCO', 'ACN', 'WMT', 'ADBE', 'VZ', 'DHR', 'TXN',
            'NEE', 'PM', 'NKE', 'RTX', 'BMY', 'UPS', 'LIN', 'QCOM', 'HON',
            'AMGN', 'LOW', 'SPGI', 'UNP', 'IBM', 'GS', 'CAT', 'INTU', 'GE',
            'AMAT', 'BKNG', 'NOW', 'PLTR', 'UBER', 'SNOW', 'ZM', 'ROKU',
            'SQ', 'SHOP', 'CRWD', 'NET', 'DDOG', 'MDB', 'FTNT', 'PANW',
            'OKTA', 'ETSY', 'RBLX', 'COIN', 'DASH', 'ABNB', 'TTD',
            'ASML', 'TSM', 'AMD', 'INTC', 'MU', 'LRCX', 'KLAC',
        ]

        nasdaq_tickers = [
            'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AVGO',
            'PEP', 'COST', 'CSCO', 'ADBE', 'NFLX', 'AMD', 'CMCSA', 'TMUS',
            'INTC', 'INTU', 'QCOM', 'AMGN', 'HON', 'AMAT', 'SBUX', 'ISRG',
            'MDLZ', 'GILD', 'ADP', 'VRTX', 'BKNG', 'MU', 'LRCX', 'REGN',
            'CSX', 'PANW', 'SNPS', 'CDNS', 'KLAC', 'NXPI', 'MAR',
            'MELI', 'ABNB', 'CTAS', 'ADI', 'LULU', 'MNST', 'ROP', 'PAYX',
            'FTNT', 'MRNA', 'ADSK', 'IDXX', 'WDAY', 'DDOG', 'PCAR', 'ODFL',
            'CRWD', 'VRSK', 'ANSS', 'FAST', 'CPRT', 'TEAM', 'ALGN',
            'DLTR', 'BIIB', 'DXCM', 'EA', 'MCHP', 'CTSH', 'TTWO', 'MRVL',
            'ZS', 'ON', 'ARM', 'DASH', 'GEHC', 'RBLX', 'APP', 'CELH',
            'COIN', 'PLTR', 'HOOD', 'ARRY',
        ]

        all_tickers = list(set(sp500_tickers + nasdaq_tickers))
        logger.info(f"Universo de acciones: {len(all_tickers)} tickers")
        return all_tickers

    def fetch_data(self, ticker: str, period: str = "2y", retries: int = 2) -> Optional[pd.DataFrame]:
        """Obtiene datos históricos con reintentos automáticos"""
        for attempt in range(retries):
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period=period, interval="1d")
                if df.empty or len(df) < 50:
                    return None
                return df
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(0.5)
                else:
                    logger.debug(f"Error fetching {ticker}: {e}")
        return None

    def get_fundamentals(self, ticker: str) -> Dict:
        """Obtiene datos fundamentales con manejo robusto de errores"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                'market_cap': info.get('marketCap', 0) or 0,
                'sector': info.get('sector', 'Unknown') or 'Unknown',
                'industry': info.get('industry', 'Unknown') or 'Unknown',
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'peg_ratio': info.get('pegRatio'),
                'revenue_growth': info.get('revenueGrowth'),
                'earnings_growth': info.get('earningsGrowth'),
                'profit_margins': info.get('profitMargins'),
                'institutional_ownership': info.get('heldPercentInstitutions', 0) or 0,
                'float': info.get('floatShares', 0) or 0,
                'avg_volume': info.get('averageVolume', 0) or 0,
                'avg_volume_10d': info.get('averageVolume10days', 0) or 0,
                'target_price': info.get('targetMeanPrice'),
                'recommendation': info.get('recommendationKey', 'none') or 'none',
                'short_ratio': info.get('shortRatio', 0) or 0,
                'beta': info.get('beta', 1.0) or 1.0,
                'name': info.get('longName', ticker) or ticker,
            }
        except Exception:
            return {'sector': 'Unknown', 'industry': 'Unknown', 'market_cap': 0, 'name': ticker}

    def calculate_technicals(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Calcula indicadores técnicos completos"""
        if df is None or len(df) < 50:
            return None

        df = df.copy()

        # Medias móviles
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA21'] = df['Close'].rolling(window=21).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()

        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle'].replace(0, np.nan)
        df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower']).replace(0, np.nan)

        # ATR
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(14).mean()
        df['ATR_Percent'] = df['ATR'] / df['Close'].replace(0, np.nan) * 100

        # Volumen
        df['Volume_MA50'] = df['Volume'].rolling(window=50).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA50'].replace(0, np.nan)

        # Rango de cierre (dónde cerró dentro del rango día)
        day_range = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Range'] = (df['Close'] - df['Low']) / day_range * 100

        # 52W + ATH
        df['52W_High'] = df['High'].rolling(window=252).max()
        df['52W_Low'] = df['Low'].rolling(window=252).min()
        df['All_Time_High'] = df['High'].cummax()
        df['Distance_ATH'] = (df['Close'] / df['All_Time_High'].replace(0, np.nan) - 1) * 100
        df['Distance_52W_High'] = (df['Close'] / df['52W_High'].replace(0, np.nan) - 1) * 100

        # Momentum
        df['Returns_1M'] = df['Close'].pct_change(21) * 100
        df['Returns_3M'] = df['Close'].pct_change(63) * 100
        df['Returns_6M'] = df['Close'].pct_change(126) * 100
        df['Returns_1Y'] = df['Close'].pct_change(252) * 100

        # Volatilidad anualizada
        df['Volatility_20D'] = df['Close'].pct_change().rolling(20).std() * np.sqrt(252) * 100

        return df

    def score_stock(self, ticker: str, df: pd.DataFrame, fundamentals: Dict) -> Optional[Dict]:
        """Puntúa una acción según criterios GROW/CANSLIM"""
        if df is None or len(df) < 200:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # --- Filtros de liquidez ---
        daily_dollar_volume = latest.get('Volume', 0) * latest.get('Close', 0)
        if daily_dollar_volume < 20_000_000:
            return None
        if latest.get('Close', 0) < 12.50:
            return None
        market_cap = fundamentals.get('market_cap', 0)
        if market_cap < 1_000_000_000:
            return None

        scores = {}
        details = {}

        # === 1. Proximidad a ATH (30%) ===
        distance_ath = latest.get('Distance_ATH', -100)
        if distance_ath > -5:
            scores['near_ath'] = 30
        elif distance_ath > -10:
            scores['near_ath'] = 20
        elif distance_ath > -15:
            scores['near_ath'] = 10
        else:
            scores['near_ath'] = 0
        details['near_ath'] = f"A {abs(distance_ath):.1f}% del ATH"

        # === 2. Tendencia de medias (20%) ===
        trend_score = 0
        if latest.get('Close', 0) > latest.get('MA10', float('inf')):
            trend_score += 5
        if latest.get('Close', 0) > latest.get('MA21', float('inf')):
            trend_score += 5
        if latest.get('Close', 0) > latest.get('MA50', float('inf')):
            trend_score += 5
        if latest.get('Close', 0) > latest.get('MA200', float('inf')):
            trend_score += 5
        scores['trend'] = trend_score

        ma10, ma21, ma50, ma200 = (latest.get('MA10', 0), latest.get('MA21', 0),
                                    latest.get('MA50', 0), latest.get('MA200', 0))
        if ma10 > ma21 > ma50 > ma200:
            details['trend'] = "Totalmente alcista (MAs alineadas)"
        elif latest.get('Close', 0) > ma50 > ma200:
            details['trend'] = "Mayormente alcista"
        elif latest.get('Close', 0) > ma200:
            details['trend'] = "Tendencia alcista débil"
        else:
            details['trend'] = "Tendencia bajista"

        # === 3. Momentum (20%) ===
        momentum_score = 0
        r1m = latest.get('Returns_1M', 0) or 0
        r3m = latest.get('Returns_3M', 0) or 0
        r6m = latest.get('Returns_6M', 0) or 0

        momentum_score += 7 if r1m > 5 else (4 if r1m > 0 else 0)
        momentum_score += 7 if r3m > 10 else (4 if r3m > 0 else 0)
        momentum_score += 6 if r6m > 20 else (3 if r6m > 0 else 0)
        scores['momentum'] = momentum_score
        details['momentum'] = f"1M: {r1m:.1f}% | 3M: {r3m:.1f}% | 6M: {r6m:.1f}%"

        # === 4. Volumen (15%) ===
        vol_ratio = latest.get('Volume_Ratio', 0) or 0
        if vol_ratio > 1.5:
            scores['volume'] = 15
            details['volume'] = f"Volumen {vol_ratio:.1f}x promedio (alto)"
        elif vol_ratio > 1.0:
            scores['volume'] = 10
            details['volume'] = f"Volumen {vol_ratio:.1f}x promedio (normal)"
        else:
            scores['volume'] = 5
            details['volume'] = f"Volumen {vol_ratio:.1f}x promedio (bajo)"

        # === 5. RSI (10%) ===
        rsi = latest.get('RSI', 50) or 50
        if 60 <= rsi <= 75:
            scores['rsi'] = 10
            details['rsi'] = f"RSI {rsi:.1f} — zona óptima"
        elif 50 <= rsi < 60:
            scores['rsi'] = 7
            details['rsi'] = f"RSI {rsi:.1f} — momentum creciendo"
        elif 75 < rsi <= 80:
            scores['rsi'] = 5
            details['rsi'] = f"RSI {rsi:.1f} — sobrecomprado leve"
        elif rsi > 80:
            scores['rsi'] = 2
            details['rsi'] = f"RSI {rsi:.1f} — sobrecomprado"
        else:
            scores['rsi'] = 3
            details['rsi'] = f"RSI {rsi:.1f} — momentum débil"

        # === 6. Consolidación/Setup (5%) ===
        volatility = latest.get('Volatility_20D', 50) or 50
        if volatility < 25:
            scores['setup'] = 5
            details['setup'] = f"Consolidación ({volatility:.1f}% vol)"
        elif volatility < 35:
            scores['setup'] = 3
            details['setup'] = f"Volatilidad moderada ({volatility:.1f}%)"
        else:
            scores['setup'] = 0
            details['setup'] = f"Volatilidad alta ({volatility:.1f}%)"

        # === 7. Fundamentales (bonus hasta 10%) ===
        fund_score = 0
        fund_details = []
        rev_growth = fundamentals.get('revenue_growth')
        if rev_growth and rev_growth > 0.20:
            fund_score += 3
            fund_details.append(f"Rev +{rev_growth*100:.0f}%")
        earn_growth = fundamentals.get('earnings_growth')
        if earn_growth and earn_growth > 0.25:
            fund_score += 4
            fund_details.append(f"EPS +{earn_growth*100:.0f}%")
        inst_own = fundamentals.get('institutional_ownership', 0) or 0
        if 0.15 <= inst_own <= 0.75:
            fund_score += 3
            fund_details.append(f"Inst {inst_own*100:.0f}%")
        scores['fundamentals'] = fund_score
        details['fundamentals'] = " | ".join(fund_details) if fund_details else "Sin datos"

        total_score = sum(scores.values())

        # === Señal de entrada ===
        signal = "NEUTRAL"
        entry_price = stop_loss = target = None

        close = latest.get('Close', 0)
        ma10 = latest.get('MA10', 0)
        ma21 = latest.get('MA21', 0)
        ma50 = latest.get('MA50', 0)
        close_range = latest.get('Close_Range', 0) or 0

        breakout_conditions = (
            close > ma10 and
            close > prev.get('Close', 0) and
            vol_ratio > 1.3 and
            close_range > 60 and
            distance_ath > -8
        )

        pullback_conditions = (
            close > ma21 and
            close < ma10 and
            rsi > 50 and
            close > ma50 and
            distance_ath > -10
        )

        if breakout_conditions:
            signal = "BREAKOUT"
            entry_price = close
            stop_loss = min(ma21, close * 0.95)
            target = close * 1.15
        elif pullback_conditions:
            signal = "PULLBACK"
            entry_price = close
            stop_loss = ma50
            target = close * 1.12

        risk = (entry_price - stop_loss) if entry_price and stop_loss else 0
        reward = (target - entry_price) if target and entry_price else 0
        r_r_ratio = round(reward / risk, 2) if risk > 0 else 0

        return {
            'ticker': ticker,
            'name': fundamentals.get('name', ticker),
            'score': round(total_score, 1),
            'scores': scores,
            'details': details,
            'price': round(float(close), 2),
            'signal': signal,
            'entry_price': round(float(entry_price), 2) if entry_price else None,
            'stop_loss': round(float(stop_loss), 2) if stop_loss else None,
            'target': round(float(target), 2) if target else None,
            'r_r_ratio': r_r_ratio,
            'distance_ath': round(float(distance_ath), 2),
            'rsi': round(float(rsi), 1),
            'returns_1m': round(float(r1m), 2),
            'returns_3m': round(float(r3m), 2),
            'returns_6m': round(float(r6m), 2),
            'volume_ratio': round(float(vol_ratio), 2),
            'sector': fundamentals.get('sector', 'Unknown'),
            'industry': fundamentals.get('industry', 'Unknown'),
            'market_cap': round(market_cap / 1_000_000_000, 2) if market_cap else 0,
            'pe_ratio': fundamentals.get('pe_ratio'),
            'revenue_growth': fundamentals.get('revenue_growth'),
            'earnings_growth': fundamentals.get('earnings_growth'),
            'atr_percent': round(float(latest.get('ATR_Percent', 0) or 0), 2),
            'volatility': round(float(volatility), 1),
            'scanned_at': datetime.now().isoformat(),
        }

    def scan(self, max_stocks: int = None, progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Escanea todas las acciones del universo.
        progress_callback(current, total, ticker, result) se llama por cada ticker.
        """
        self.scan_status.update({
            'running': True,
            'progress': 0,
            'error': None,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
        })

        tickers = self.universe[:max_stocks] if max_stocks else self.universe
        self.scan_status['total'] = len(tickers)
        results = []

        for i, ticker in enumerate(tickers, 1):
            self.scan_status.update({'progress': i, 'current_ticker': ticker})

            df = self.fetch_data(ticker, period="2y")
            if df is None:
                if progress_callback:
                    progress_callback(i, len(tickers), ticker, None)
                continue

            df = self.calculate_technicals(df)
            if df is None:
                if progress_callback:
                    progress_callback(i, len(tickers), ticker, None)
                continue

            fundamentals = self.get_fundamentals(ticker)
            result = self.score_stock(ticker, df, fundamentals)

            if result:
                results.append(result)
                logger.info(f"[{i}/{len(tickers)}] {ticker} — Score: {result['score']} | {result['signal']}")
            else:
                logger.debug(f"[{i}/{len(tickers)}] {ticker} — No califica")

            if progress_callback:
                progress_callback(i, len(tickers), ticker, result)

            # Pequeña pausa para no saturar la API
            time.sleep(0.1)

        results.sort(key=lambda x: x['score'], reverse=True)
        self.results = results
        self.scan_status.update({
            'running': False,
            'end_time': datetime.now().isoformat(),
        })

        logger.info(f"Scan completado: {len(results)} acciones calificadas de {len(tickers)} escaneadas")
        return results
