import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type LineData,
  type SeriesMarker,
  type UTCTimestamp
} from "lightweight-charts";
import type { PriceCandle, TimelineEvent } from "../../types";

type ChartMode = "candles" | "line";

type IndicatorState = {
  ma7: boolean;
  ma20: boolean;
  volume: boolean;
  events: boolean;
};

type Props = {
  candles: PriceCandle[];
  events: TimelineEvent[];
  mode: ChartMode;
  indicators: IndicatorState;
  isLoading: boolean;
};

type MarkerSeries = {
  setMarkers: (data: SeriesMarker<UTCTimestamp>[]) => void;
};

export function TradingChart({ candles, events, mode, indicators, isLoading }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    const chart: IChartApi = createChart(containerRef.current, {
      height: 430,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#637083"
      },
      grid: {
        vertLines: { color: "#edf0f4" },
        horzLines: { color: "#edf0f4" }
      },
      rightPriceScale: {
        borderColor: "#d8dee8",
        scaleMargins: { top: 0.08, bottom: indicators.volume ? 0.28 : 0.08 }
      },
      timeScale: {
        borderColor: "#d8dee8",
        timeVisible: true
      },
      crosshair: {
        mode: 0
      }
    });

    const candleData: CandlestickData<UTCTimestamp>[] = candles
      .filter((item) => item.open !== null && item.high !== null && item.low !== null && item.close !== null)
      .map((item) => ({
        time: toChartTime(item.opened_at),
        open: item.open as number,
        high: item.high as number,
        low: item.low as number,
        close: item.close as number
      }))
      .sort((a, b) => a.time - b.time);

    let markerTarget: MarkerSeries | null = null;
    if (mode === "candles") {
      const mainSeries = chart.addCandlestickSeries({
        upColor: "#0f7b6c",
        downColor: "#b42318",
        borderUpColor: "#0f7b6c",
        borderDownColor: "#b42318",
        wickUpColor: "#0f7b6c",
        wickDownColor: "#b42318",
        priceLineVisible: false
      });
      mainSeries.setData(candleData);
      markerTarget = mainSeries;
    } else {
      const mainSeries = chart.addLineSeries({
        color: "#15202b",
        lineWidth: 2,
        priceLineVisible: false
      });
      mainSeries.setData(
        candles
          .filter((item) => item.close !== null)
          .map((item) => ({ time: toChartTime(item.opened_at), value: item.close as number }))
          .sort((a, b) => a.time - b.time)
      );
      markerTarget = mainSeries;
    }

    if (indicators.volume) {
      const volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
        priceLineVisible: false
      });
      const volumeData: HistogramData<UTCTimestamp>[] = candles
        .filter((item) => (item.volume_usd ?? item.volume_quote) !== null && (item.volume_usd ?? item.volume_quote) !== undefined)
        .map((item) => ({
          time: toChartTime(item.opened_at),
          value: (item.volume_usd ?? item.volume_quote) as number,
          color: (item.close ?? 0) >= (item.open ?? 0) ? "rgba(15, 123, 108, 0.35)" : "rgba(180, 35, 24, 0.28)"
        }))
        .sort((a, b) => a.time - b.time);
      volumeSeries.setData(volumeData);
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
    }

    if (indicators.ma7) {
      addMovingAverage(chart, candles, "ma7", "#2563eb");
    }
    if (indicators.ma20) {
      addMovingAverage(chart, candles, "ma20", "#b06a00");
    }
    if (indicators.events && markerTarget) {
      markerTarget.setMarkers(toMarkers(events));
    }

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) chart.applyOptions({ width });
    });
    observer.observe(containerRef.current);
    chart.timeScale().fitContent();

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [candles, events, indicators.events, indicators.ma20, indicators.ma7, indicators.volume, mode]);

  if (isLoading) {
    return <div className="flex h-[430px] items-center justify-center text-sm text-muted">차트 로드 중</div>;
  }

  if (candles.length === 0) {
    return <div className="flex h-[430px] items-center justify-center text-sm text-muted">가격 캔들 데이터가 없습니다.</div>;
  }

  return <div className="h-[430px] min-w-0 w-full" ref={containerRef} />;
}

function addMovingAverage(chart: IChartApi, candles: PriceCandle[], key: "ma7" | "ma20", color: string) {
  const series = chart.addLineSeries({
    color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false
  });
  const rows: LineData<UTCTimestamp>[] = candles
    .filter((item) => item[key] !== null)
    .map((item) => ({ time: toChartTime(item.opened_at), value: item[key] as number }))
    .sort((a, b) => a.time - b.time);
  series.setData(rows);
}

function toMarkers(events: TimelineEvent[]): SeriesMarker<UTCTimestamp>[] {
  return events
    .slice(0, 50)
    .map((event) => ({
      id: String(event.id),
      time: toChartTime(event.occurred_at),
      position: event.severity === "high" ? ("aboveBar" as const) : ("belowBar" as const),
      color: event.severity === "high" ? "#b42318" : event.severity === "medium" ? "#b06a00" : "#0f7b6c",
      shape: event.event_type === "price_move" ? ("arrowDown" as const) : ("circle" as const),
      text: event.event_type.replace("_", " ")
    }))
    .sort((a, b) => a.time - b.time);
}

function toChartTime(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}
