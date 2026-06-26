import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

const COLORS = {
  gas: '#38bdf8',
  oil: '#fbbf24',
  gasReq: '#0ea5e9',
  oilReq: '#f59e0b',
}

export default function SizingChart({ result, separatorType }) {
  const data = result.curve_data || []
  if (!data.length) return null

  const isVertical = separatorType === 'vertical'
  const xKey = isVertical ? 'diameter_in' : 'length_ft'
  const xLabel = isVertical ? 'Diameter (in)' : 'Length (ft)'

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-md">
      <h3 className="mb-1 text-sm font-semibold text-white">Capacity vs. {xLabel.split(' ')[0]}</h3>
      <p className="mb-4 text-xs text-slate-400">
        {isVertical
          ? 'Gas and oil capacity curves at selected shell height'
          : `Gas and oil capacity at ${result.diameter_in}" diameter`}
      </p>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey={xKey}
              stroke="#94a3b8"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              label={{ value: xLabel, position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 11 }}
            />
            <YAxis
              yAxisId="gas"
              stroke={COLORS.gas}
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              label={{ value: 'Gas (MMscfd)', angle: -90, position: 'insideLeft', fill: COLORS.gas, fontSize: 11 }}
            />
            <YAxis
              yAxisId="oil"
              orientation="right"
              stroke={COLORS.oil}
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              label={{ value: 'Oil (BOPD)', angle: 90, position: 'insideRight', fill: COLORS.oil, fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line
              yAxisId="gas"
              type="monotone"
              dataKey="gas_capacity_mmscfd"
              name="Gas capacity"
              stroke={COLORS.gas}
              strokeWidth={2}
              dot={false}
            />
            <Line
              yAxisId="oil"
              type="monotone"
              dataKey="oil_capacity_bopd"
              name="Oil capacity"
              stroke={COLORS.oil}
              strokeWidth={2}
              dot={false}
            />
            <ReferenceLine
              yAxisId="gas"
              y={data[0]?.required_gas_mmscfd}
              stroke={COLORS.gasReq}
              strokeDasharray="6 4"
              label={{ value: 'Required gas', fill: COLORS.gasReq, fontSize: 10 }}
            />
            <ReferenceLine
              yAxisId="oil"
              y={data[0]?.required_oil_bopd}
              stroke={COLORS.oilReq}
              strokeDasharray="6 4"
              label={{ value: 'Required oil', fill: COLORS.oilReq, fontSize: 10 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
