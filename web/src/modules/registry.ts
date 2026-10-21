// The widget registry: maps a widget type from a module layout to the component that draws it.
// Adding a widget type = one component in widgets.tsx + one line here (+ the API schema).

import type { ComponentType } from 'react'

import {
  AlertListWidget,
  InputsSummaryWidget,
  PredictedProblemsWidget,
  TextNoteWidget,
  TilesWidget,
  TrendChartWidget,
  UnknownWidget,
} from './widgets'
import type { WidgetProps } from './widgets'

export const WIDGETS: Record<string, ComponentType<WidgetProps>> = {
  input_group: TilesWidget,
  value_tiles: TilesWidget,
  inputs_summary: InputsSummaryWidget,
  predicted_problems: PredictedProblemsWidget,
  alert_list: AlertListWidget,
  trend_chart: TrendChartWidget,
  text_note: TextNoteWidget,
}

/** Unknown types (e.g. added on the server before the web app is updated) get a placeholder. */
export function widgetFor(type: string): ComponentType<WidgetProps> {
  return WIDGETS[type] ?? UnknownWidget
}
