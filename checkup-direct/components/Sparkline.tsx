/**
 * Sparkline — lightweight SVG price trend line.
 * Pass an array of numbers (prices), renders a colored line chart.
 */
import React from 'react';
import { View } from 'react-native';
import Svg, { Polyline, Line, Defs, LinearGradient, Stop, Path } from 'react-native-svg';
import { Colors } from '@/constants/Colors';

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  showArea?: boolean;
}

export function Sparkline({ data, width = 80, height = 32, color, showArea = true }: SparklineProps) {
  if (!data || data.length < 2) {
    return <View style={{ width, height }} />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * w;
    const y = pad + h - ((v - min) / range) * h;
    return `${x},${y}`;
  });

  const trend = data[data.length - 1] >= data[0];
  const lineColor = color || (trend ? Colors.green : Colors.red);

  // Area path
  const firstX = pad;
  const lastX = pad + w;
  const bottom = pad + h;
  const areaPath = `M ${points[0]} L ${points.join(' L ')} L ${lastX},${bottom} L ${firstX},${bottom} Z`;

  return (
    <Svg width={width} height={height}>
      <Defs>
        <LinearGradient id={`sg_${width}`} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={lineColor} stopOpacity="0.3" />
          <Stop offset="1" stopColor={lineColor} stopOpacity="0" />
        </LinearGradient>
      </Defs>

      {showArea && (
        <Path d={areaPath} fill={`url(#sg_${width})`} />
      )}

      <Polyline
        points={points.join(' ')}
        fill="none"
        stroke={lineColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
