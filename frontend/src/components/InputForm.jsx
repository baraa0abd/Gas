function Field({ label, unit, children, hint }) {
  return (
    <label className="block">
      <span className="mb-1 flex items-baseline justify-between text-xs font-medium text-slate-300">
        {label}
        {unit && <span className="font-mono text-slate-500">{unit}</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>}
    </label>
  )
}

function NumberInput({ value, onChange, step = 'any', min, max }) {
  return (
    <input
      type="number"
      step={step}
      min={min}
      max={max}
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      className="w-full rounded-lg border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none ring-petroleum-500 transition focus:border-petroleum-500 focus:ring-1"
    />
  )
}

export default function InputForm({ form, onChange, onSubmit, loading, retentionNote }) {
  const is3Phase = form.phase_mode === '3-phase'
  const isVertical = form.separator_type === 'vertical'

  return (
    <form
      onSubmit={onSubmit}
      className="sticky top-6 h-fit space-y-5 rounded-2xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-md"
    >
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-petroleum-100">
          Separator Configuration
        </h2>
        <div className="grid grid-cols-2 gap-2">
          {['vertical', 'horizontal'].map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => onChange('separator_type', type)}
              className={`rounded-lg px-3 py-2 text-sm capitalize transition ${
                form.separator_type === type
                  ? 'bg-petroleum-600 text-white shadow-lg shadow-petroleum-900/50'
                  : 'bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {['2-phase', '3-phase'].map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => onChange('phase_mode', mode)}
              className={`rounded-lg px-3 py-2 text-sm transition ${
                form.phase_mode === mode
                  ? 'bg-petroleum-600 text-white'
                  : 'bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-petroleum-100">
          Flow Rates
        </h2>
        <div className="space-y-3">
          <Field label="Gas rate" unit="MMscfd">
            <NumberInput value={form.gas_mmscfd} onChange={(v) => onChange('gas_mmscfd', v)} min={0} />
          </Field>
          <Field label="Oil rate" unit="BOPD">
            <NumberInput value={form.oil_bopd} onChange={(v) => onChange('oil_bopd', v)} min={0} />
          </Field>
          {is3Phase && (
            <Field label="Water rate" unit="BPD">
              <NumberInput value={form.water_bpd} onChange={(v) => onChange('water_bpd', v)} min={0} />
            </Field>
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-petroleum-100">
          Fluid Properties
        </h2>
        <div className="space-y-3">
          <Field label="Oil API gravity" unit="°API">
            <NumberInput value={form.api_gravity} onChange={(v) => onChange('api_gravity', v)} />
          </Field>
          <Field label="Gas specific gravity" unit="air = 1">
            <NumberInput value={form.sg_gas} onChange={(v) => onChange('sg_gas', v)} step="0.01" />
          </Field>
          {is3Phase && (
            <Field label="Water specific gravity">
              <NumberInput value={form.sg_water} onChange={(v) => onChange('sg_water', v)} step="0.01" />
            </Field>
          )}
          <Field label="Operating pressure" unit="psia">
            <NumberInput value={form.pressure_psia} onChange={(v) => onChange('pressure_psia', v)} min={0} />
          </Field>
          <Field label="Operating temperature" unit="°F">
            <NumberInput value={form.temperature_f} onChange={(v) => onChange('temperature_f', v)} />
          </Field>
          <Field label="Z-factor">
            <NumberInput value={form.z_factor} onChange={(v) => onChange('z_factor', v)} step="0.01" min={0.1} max={2} />
          </Field>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-petroleum-100">
          Design Parameters
        </h2>
        <div className="space-y-3">
          <Field label="K constant" hint={isVertical ? 'Default 0.167 for vertical' : 'Default 0.45 for horizontal'}>
            <NumberInput value={form.k_factor} onChange={(v) => onChange('k_factor', v)} step="0.001" />
          </Field>
          {isVertical ? (
            <Field label="Shell height" unit="ft" hint="Liquid height h from slide 10 lookup">
              <NumberInput value={form.shell_height_ft} onChange={(v) => onChange('shell_height_ft', v)} min={5} />
            </Field>
          ) : (
            <Field label="Liquid fill fraction" unit="f_liq" hint="Typically 0.5 (half full)">
              <NumberInput
                value={form.liquid_fraction}
                onChange={(v) => onChange('liquid_fraction', v)}
                step="0.05"
                min={0.25}
                max={0.75}
              />
            </Field>
          )}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-petroleum-100">
            Retention Time
          </h2>
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={form.custom_retention}
              onChange={(e) => onChange('custom_retention', e.target.checked)}
              className="rounded border-white/20 bg-slate-800 text-petroleum-500"
            />
            Custom
          </label>
        </div>
        {!form.custom_retention && retentionNote && (
          <p className="mb-2 rounded-lg bg-petroleum-900/40 px-2 py-1.5 text-[11px] text-petroleum-100">
            {retentionNote}
          </p>
        )}
        <div className="space-y-3">
          <Field label="Oil retention" unit="min">
            <NumberInput
              value={form.retention_oil_min}
              onChange={(v) => onChange('retention_oil_min', v)}
              min={0.1}
              step="0.5"
            />
          </Field>
          {is3Phase && (
            <Field label="Water retention" unit="min">
              <NumberInput
                value={form.retention_water_min}
                onChange={(v) => onChange('retention_water_min', v)}
                min={0.1}
                step="0.5"
              />
            </Field>
          )}
        </div>
      </section>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-xl bg-petroleum-600 py-3 text-sm font-semibold text-white shadow-lg shadow-petroleum-900/60 transition hover:bg-petroleum-500 disabled:opacity-60"
      >
        {loading ? 'Calculating…' : 'Run Sizing'}
      </button>
    </form>
  )
}
