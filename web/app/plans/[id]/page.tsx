"use client";

import { Alert, Button, Skeleton, Space } from "antd";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import PlanView from "@/components/PlanView";
import { ApiError, getPlan, type PlanDocument } from "@/lib/api";
import { WAKING } from "@/lib/copy";
import { useSlow } from "@/lib/useSlow";

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<PlanDocument | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const slow = useSlow(!doc && !error);

  const load = useCallback(() => {
    setError(null);
    getPlan(id)
      .then(setDoc)
      .catch((e) => setError(e instanceof ApiError ? e : new ApiError(0, String(e))));
  }, [id]);

  useEffect(load, [load]);

  let body;
  if (doc) {
    body = <PlanView doc={doc} />;
  } else if (error?.status === 404) {
    body = (
      <Space direction="vertical">
        <div>No plan with this link.</div>
        <Link href="/">Plan a trip</Link>
      </Space>
    );
  } else if (error) {
    body = (
      <Space direction="vertical">
        <Alert type="error" message={error.detail} showIcon={false} />
        <Button onClick={load}>Try again</Button>
      </Space>
    );
  } else {
    body = (
      <>
        {slow && <Alert type="info" message={WAKING} showIcon={false} style={{ marginBottom: 12 }} />}
        <Skeleton active />
      </>
    );
  }

  return (
    <main>
      <div style={{ marginBottom: 8 }}>
        <Link href="/">Fuel planner</Link>
      </div>
      {body}
    </main>
  );
}
