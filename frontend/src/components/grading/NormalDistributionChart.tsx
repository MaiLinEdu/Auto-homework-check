"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface Props {
  mean: number;
  stdDev: number;
  studentScore: number;
  totalPossible: number;
  label?: string;
}

function normalPdf(x: number, mean: number, std: number): number {
  const exp = -0.5 * ((x - mean) / std) ** 2;
  return (1 / (std * Math.sqrt(2 * Math.PI))) * Math.E ** exp;
}

export default function NormalDistributionChart({
  mean,
  stdDev,
  studentScore,
  totalPossible,
  label = "Student",
}: Props) {
  const std = stdDev > 0 ? stdDev : totalPossible * 0.15;
  const minX = Math.max(0, mean - 3.5 * std);
  const maxX = Math.min(totalPossible, mean + 3.5 * std);
  const step = (maxX - minX) / 80;

  const data = [];
  for (let x = minX; x <= maxX; x += step) {
    data.push({
      score: Math.round(x * 10) / 10,
      density: normalPdf(x, mean, std),
    });
  }

  const percentile = computePercentile(studentScore, mean, std);

  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="score"
            tick={{ fontSize: 11 }}
            label={{ value: "Score", position: "insideBottomRight", offset: -5, fontSize: 11 }}
          />
          <YAxis hide />
          <Tooltip
            formatter={(value: number) => [value.toFixed(4), "Density"]}
            labelFormatter={(l) => `Score: ${l}`}
          />
          <Area
            type="monotone"
            dataKey="density"
            stroke="#3b82f6"
            fill="#dbeafe"
            fillOpacity={0.6}
          />
          <ReferenceLine
            x={Math.round(studentScore * 10) / 10}
            stroke="#ef4444"
            strokeWidth={2}
            strokeDasharray="4 4"
            label={{
              value: `${label}: ${studentScore}`,
              position: "top",
              fill: "#ef4444",
              fontSize: 11,
            }}
          />
          <ReferenceLine
            x={Math.round(mean * 10) / 10}
            stroke="#6b7280"
            strokeDasharray="3 3"
            label={{
              value: `Mean: ${mean.toFixed(1)}`,
              position: "top",
              fill: "#6b7280",
              fontSize: 11,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
      <p className="text-center text-sm text-gray-600">
        Percentile: <span className="font-semibold text-primary-700">{percentile}th</span>
        {" | "}Mean: {mean.toFixed(1)} | SD: {std.toFixed(1)}
      </p>
    </div>
  );
}

function computePercentile(score: number, mean: number, std: number): number {
  // Approximate CDF using error function approximation
  const z = (score - mean) / std;
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989422804014327;
  const p =
    d *
    Math.exp((-z * z) / 2) *
    (t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))));
  const cdf = z > 0 ? 1 - p : p;
  return Math.round(cdf * 100);
}
