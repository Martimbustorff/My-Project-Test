/**
 * Gauge — SVG semi-circle consensus score meter.
 * Score range: -1.0 (STRONG SELL) to +1.0 (STRONG BUY)
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path, Circle, Text as SvgText, Defs, LinearGradient, Stop } from 'react-native-svg';
import { Colors, recColor } from '@/constants/Colors';

interface GaugeProps {
  score: number;          // -1.0 to 1.0
  recommendation: string;
  size?: number;          // diameter (default 180)
  showLabel?: boolean;
}

export function Gauge({ score, recommendation, size = 180, showLabel = true }: GaugeProps) {
  const R = size * 0.38;
  const cx = size / 2;
  const cy = size * 0.55;
  const strokeWidth = size * 0.07;

  // Semi-circle: from 180° to 0° (left to right)
  // Map score -1→1 to angle 180°→0°
  const clampedScore = Math.max(-1, Math.min(1, score));
  const angleDeg = 180 - ((clampedScore + 1) / 2) * 180; // 180° at -1, 0° at +1
  const angleRad = (angleDeg * Math.PI) / 180;

  // Background arc (full semi-circle)
  const bgStart = { x: cx - R, y: cy };
  const bgEnd = { x: cx + R, y: cy };
  const bgPath = `M ${bgStart.x} ${bgStart.y} A ${R} ${R} 0 0 1 ${bgEnd.x} ${bgEnd.y}`;

  // Filled arc (from left to score position)
  const needleX = cx + R * Math.cos(Math.PI - angleRad);
  const needleY = cy - R * Math.sin(Math.PI - angleRad);

  // Arc goes from far left to needle position
  const arcAngleRad = ((clampedScore + 1) / 2) * Math.PI; // 0 at -1, π at +1
  const fillEndX = cx + R * Math.cos(Math.PI - arcAngleRad);
  const fillEndY = cy - R * Math.sin(Math.PI - arcAngleRad);
  const largeArc = arcAngleRad > Math.PI / 2 ? 1 : 0;
  const fillPath = arcAngleRad > 0.01
    ? `M ${bgStart.x} ${bgStart.y} A ${R} ${R} 0 ${largeArc} 1 ${fillEndX} ${fillEndY}`
    : '';

  const color = recColor(recommendation);

  return (
    <View style={{ alignItems: 'center', width: size }}>
      <Svg width={size} height={size * 0.62}>
        <Defs>
          <LinearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor={Colors.strongSell} stopOpacity="1" />
            <Stop offset="0.25" stopColor={Colors.sell} stopOpacity="1" />
            <Stop offset="0.5" stopColor={Colors.hold} stopOpacity="1" />
            <Stop offset="0.75" stopColor={Colors.buy} stopOpacity="1" />
            <Stop offset="1" stopColor={Colors.strongBuy} stopOpacity="1" />
          </LinearGradient>
        </Defs>

        {/* Background track */}
        <Path
          d={bgPath}
          stroke={Colors.border}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
        />

        {/* Colored fill arc */}
        {fillPath ? (
          <Path
            d={fillPath}
            stroke={color}
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
            opacity={0.85}
          />
        ) : null}

        {/* Needle dot */}
        <Circle
          cx={fillEndX || bgStart.x}
          cy={fillEndY || bgStart.y}
          r={strokeWidth * 0.7}
          fill={color}
        />

        {/* Center score text */}
        <SvgText
          x={cx}
          y={cy + 2}
          textAnchor="middle"
          fontSize={size * 0.13}
          fontWeight="bold"
          fill={color}
        >
          {clampedScore >= 0 ? '+' : ''}{clampedScore.toFixed(2)}
        </SvgText>

        {/* Scale labels */}
        <SvgText x={cx - R - 4} y={cy + 14} textAnchor="end" fontSize={size * 0.065} fill={Colors.textMuted}>SELL</SvgText>
        <SvgText x={cx + R + 4} y={cy + 14} textAnchor="start" fontSize={size * 0.065} fill={Colors.textMuted}>BUY</SvgText>
      </Svg>

      {showLabel && (
        <Text style={[styles.label, { color, fontSize: size * 0.085 }]}>
          {recommendation}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontWeight: '800',
    letterSpacing: 1,
    marginTop: -4,
  },
});
