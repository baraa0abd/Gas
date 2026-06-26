function Stat({ label, value, unit, highlight }) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight
          ? 'border-petroleum-500/50 bg-petroleum-900/30'
          : 'border-white/10 bg-white/5'
      }`}
    >
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="mt-1 font-mono text-2xl font-semibold text-white">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-400">{unit}</span>}
      </dd>
    </div>
  )
}

export default function ResultsPanel({ result, form }) {
  const isVertical = result.separator_type === 'vertical'

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-md">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Recommended Vessel Size</h2>
            <p className="text-sm text-slate-400">
              {result.phase_mode} · {result.separator_type} separator
            </p>
          </div>
          <span className="rounded-full bg-amber-500/20 px-3 py-1 text-xs font-medium text-amber-200">
            Governing: {result.governing_constraint}
          </span>
        </div>

        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Diameter" value={result.diameter_in} unit="in" highlight />
          <Stat
            label={isVertical ? 'Shell height' : 'Seam-to-seam length'}
            value={result.length_ft}
            unit="ft"
            highlight
          />
          <Stat label="Liquid height" value={result.liquid_height_ft} unit="ft" />
          <Stat label="L/D ratio" value={result.ld_ratio} unit="" />
        </dl>

        <p className="mt-4 font-mono text-sm text-petroleum-100">
          {result.diameter_in}&quot; × {result.length_ft}&apos;{' '}
          {isVertical ? 'vertical' : 'horizontal'} separator
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">Design Constraints</h3>
          <ul className="space-y-3">
            {result.constraints.map((c) => (
              <li
                key={c.name}
                className={`rounded-lg border px-3 py-2.5 text-sm ${
                  c.governing
                    ? 'border-petroleum-500/40 bg-petroleum-900/20'
                    : 'border-white/5 bg-black/20'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{c.name}</span>
                  {c.governing && (
                    <span className="text-[10px] uppercase tracking-wide text-petroleum-300">
                      Governing
                    </span>
                  )}
                </div>
                <p className="mt-1 font-mono text-xs text-slate-400">{c.formula}</p>
                <p className="mt-1 text-slate-300">
                  Capacity:{' '}
                  <span className="font-mono text-white">
                    {c.capacity_value.toLocaleString()} {c.capacity_unit}
                  </span>
                </p>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">Fluid Properties @ Operating Conditions</h3>
          <dl className="space-y-2 text-sm">
            {Object.entries(result.fluid_summary).map(([key, val]) => (
              <div key={key} className="flex justify-between border-b border-white/5 py-1.5">
                <dt className="text-slate-400">{key.replace(/_/g, ' ')}</dt>
                <dd className="font-mono text-white">{val}</dd>
              </div>
            ))}
          </dl>

          <h3 className="mb-2 mt-5 text-sm font-semibold text-white">Retention</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between py-1">
              <dt className="text-slate-400">Oil retention</dt>
              <dd className="font-mono text-white">{result.retention_summary.oil_minutes} min</dd>
            </div>
            {result.retention_summary.water_minutes != null && (
              <div className="flex justify-between py-1">
                <dt className="text-slate-400">Water retention</dt>
                <dd className="font-mono text-white">{result.retention_summary.water_minutes} min</dd>
              </div>
            )}
            {result.retention_summary.note && (
              <p className="text-xs text-slate-500">{result.retention_summary.note}</p>
            )}
          </dl>

          <h3 className="mb-2 mt-5 text-sm font-semibold text-white">Your Feed</h3>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-400">Gas</dt>
              <dd className="font-mono">{form.gas_mmscfd} MMscfd</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Oil</dt>
              <dd className="font-mono">{form.oil_bopd} BOPD</dd>
            </div>
            {form.phase_mode === '3-phase' && (
              <div className="flex justify-between">
                <dt className="text-slate-400">Water</dt>
                <dd className="font-mono">{form.water_bpd} BPD</dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  )
}
