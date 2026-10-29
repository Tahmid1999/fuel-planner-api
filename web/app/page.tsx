"use client";

import { Alert, Skeleton, Typography } from "antd";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import PlanForm from "@/components/PlanForm";
import { type ActivePrices, activePrices, getPlan, type PlanDocument } from "@/lib/api";
import { asOf } from "@/lib/format";

function PricesLine() {
  const [prices, setPrices] = useState<ActivePrices | null>(null);
  useEffect(() => {
    activePrices()
      .then(setPrices)
      .catch(() => setPrices(null));
  }, []);
  if (!prices) return null;
  return (
    <Typography.Text type="secondary">
      Prices: {prices.source}, as of {asOf(prices.as_of)} ·{" "}
      <span className="num">{prices.station_count.toLocaleString("en-US")}</span> truck stops
    </Typography.Text>
  );
}

function Trip() {
  const planId = useSearchParams().get("plan");
  const [saved, setSaved] = useState<PlanDocument | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!planId) return;
    getPlan(planId)
      .then(setSaved)
      .catch(() => setFailed(true));
  }, [planId]);

  if (planId && !saved && !failed) return <Skeleton active />;
  return (
    <>
      {failed && (
        <Alert
          type="warning"
          message="Couldn't load that plan; start a new one."
          showIcon={false}
          style={{ marginBottom: 12 }}
        />
      )}
      <PlanForm
        key={saved?.id ?? "new"}
        initial={saved ? { from: saved.from, to: saved.to, inputs: saved.inputs } : undefined}
      />
    </>
  );
}

export default function Home() {
  return (
    <main>
      <Typography.Title level={4} style={{ marginTop: 4 }}>
        Fuel planner
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        Cheapest diesel stops between two US cities, for your truck and tank.
      </Typography.Paragraph>
      <Suspense fallback={<Skeleton active />}>
        <Trip />
      </Suspense>
      <div style={{ marginTop: 16 }}>
        <PricesLine />
      </div>
    </main>
  );
}
