"use client";

import { Alert, Button, Col, Collapse, Form, InputNumber, Row } from "antd";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, type CityChoice, createPlan, type PlanInputs } from "@/lib/api";
import { WAKING } from "@/lib/copy";
import { checkInputs, DEFAULT_INPUTS, loadTruck, saveTruck } from "@/lib/truck";
import { useSlow } from "@/lib/useSlow";

import CityInput from "./CityInput";

type Values = PlanInputs & { from: CityChoice | null; to: CityChoice | null };
type Initial = { from: CityChoice; to: CityChoice; inputs: PlanInputs };

const LIMIT_FIELDS = ["reserve_pct", "max_detour_mi"];
// API field names that differ from the form's
const FIELD_NAMES: Record<string, string> = { from_city: "from", to_city: "to" };

export default function PlanForm({ initial }: { initial?: Initial }) {
  const [form] = Form.useForm<Values>();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limitsOpen, setLimitsOpen] = useState(false);
  const slow = useSlow(pending);

  // localStorage only exists in the browser, so the saved truck is applied
  // after the first render.
  useEffect(() => {
    if (!initial) form.setFieldsValue(loadTruck());
  }, [form, initial]);

  function showErrors(errors: Record<string, string | string[]>) {
    const names = Object.keys(errors);
    form.setFields(
      names.map((name) => ({
        name: (FIELD_NAMES[name] ?? name) as keyof Values,
        errors: ([] as string[]).concat(errors[name]),
      })),
    );
    if (names.some((n) => LIMIT_FIELDS.includes(n))) setLimitsOpen(true);
  }

  async function submit(values: Values) {
    setError(null);
    const inputs: PlanInputs = {
      mpg: values.mpg,
      tank_gal: values.tank_gal,
      start_pct: values.start_pct,
      reserve_pct: values.reserve_pct,
      max_detour_mi: values.max_detour_mi,
    };
    const errors: Record<string, string> = { ...checkInputs(inputs) };
    if (!values.from) errors.from = "pick a city from the list";
    if (!values.to) errors.to = "pick a city from the list";
    else if (values.from && values.from.id === values.to.id) {
      errors.to = "pick a different city from the start";
    }
    if (Object.keys(errors).length) return showErrors(errors);

    setPending(true);
    try {
      const doc = await createPlan({ from_city: values.from!.id, to_city: values.to!.id, ...inputs });
      saveTruck(inputs);
      router.push(`/plans/${doc.id}`);
    } catch (e) {
      if (!(e instanceof ApiError)) throw e;
      const fields = Object.keys(e.fields).filter((k) => k !== "non_field_errors");
      if (fields.length) showErrors(e.fields);
      setError(e.fields.non_field_errors?.[0] ?? (fields.length ? null : e.detail));
      setPending(false);
    }
  }

  const number = (name: keyof PlanInputs, label: string, step = 1) => (
    <Form.Item name={name} label={label}>
      <InputNumber step={step} style={{ width: "100%" }} className="num" />
    </Form.Item>
  );

  return (
    <Form
      form={form}
      name="trip"
      layout="vertical"
      requiredMark={false}
      initialValues={initial ? { ...initial.inputs, from: initial.from, to: initial.to } : DEFAULT_INPUTS}
      onFinish={submit}
      // every edit clears that field's old error
      onValuesChange={(changed) => {
        const stale = (Object.keys(changed) as (keyof Values)[]).filter(
          (name) => form.getFieldError(name).length,
        );
        if (stale.length) form.setFields(stale.map((name) => ({ name, errors: [] })));
      }}
    >
      <Row gutter={12}>
        <Col xs={24} sm={12}>
          <Form.Item name="from" label="From">
            <CityInput placeholder="City, state" />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item name="to" label="To">
            <CityInput placeholder="City, state" />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col xs={8}>{number("mpg", "Miles per gallon", 0.1)}</Col>
        <Col xs={8}>{number("tank_gal", "Tank (gal)", 10)}</Col>
        <Col xs={8}>{number("start_pct", "Tank now (%)", 5)}</Col>
      </Row>
      <Collapse
        size="small"
        activeKey={limitsOpen ? ["limits"] : []}
        onChange={(keys) => setLimitsOpen(keys.includes("limits"))}
        style={{ marginBottom: 16 }}
        items={[
          {
            key: "limits",
            label: "Limits",
            forceRender: true,
            children: (
              <Row gutter={12}>
                <Col xs={12}>{number("reserve_pct", "Keep in reserve (%)")}</Col>
                <Col xs={12}>{number("max_detour_mi", "Max detour off the route (mi)")}</Col>
              </Row>
            ),
          },
        ]}
      />
      {error && <Alert type="error" message={error} showIcon={false} style={{ marginBottom: 12 }} />}
      {slow && <Alert type="info" message={WAKING} showIcon={false} style={{ marginBottom: 12 }} />}
      <Button type="primary" htmlType="submit" loading={pending} block>
        Plan trip
      </Button>
    </Form>
  );
}
