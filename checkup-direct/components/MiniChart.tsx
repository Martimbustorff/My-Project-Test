import React from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import Svg, { Polyline, Defs, LinearGradient, Stop, Path, Text as SvgText } from 'react-native-svg';
import { Colors } from '@/constants/Colors';

interface DataPoint { timestamp: string; value: number }

interface Props {
  data: DataPoint[];
  height?: number;
  color?: string;
}

export function MiniChart({ data, height = 120, color = Colors.primary }: Props) {
  const width = Dimensions.get('window').width - 48;

  if (!data || data.length < 2) {
    return <View style={[styles.empty, { height }]} />;
  }

  const values = data.map(d => d.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  const pad = 8;
  const chartW = width - pad * 2;
  const chartH = height - pad * 2;

  const points = data.map((d, i) => {
    const x = pad + (i / (data.length - 1)) * chartW;
    const y = pad + chartH - ((d.value - minV) / range) * chartH;
    return `${x},${y}`;
  }).join(' ');

  const isPositive = values[values.length - 1] >= values[0];
  const lineColor = isPositive ? Colors.green : Colors.red;

  // Build path for area fill
  const firstPt = data[0];
  const lastPt  = data[data.length - 1];
  const fx = pad;
  const lx = pad + chartW;
  const baseline = pad + chartH;
  const areaPath = `M ${fx},${baseline} ${points} L ${lx},${baseline} Z`;

  return (
    <View style={{ height, width }}>
      <Svg width={width} height={height}>
        <Defs>
          <LinearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0%" stopColor={lineColor} stopOpacity="0.3" />
            <Stop offset="100%" stopColor={lineColor} stopOpacity="0.0" />
          </LinearGradient>
        </Defs>
        <Path d={areaPath} fill="url(#grad)" />
        <Polyline
          points={points}
          fill="none"
          stroke={lineColor}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  empty: {
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
