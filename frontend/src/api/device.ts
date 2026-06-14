const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type DeviceOverviewResponse = {
  member: {
    member_id: string;
    name: string;
    relation: string;
  };
  device: {
    device_name: string;
    device_status: string;
    battery_level: number;
    last_sync_at: string | null;
  };
  summary: {
    steps: number;
    steps_target: number;
    avg_heart_rate: number;
    heart_rate_range_text: string;
    sleep_hours: number;
    sleep_target: number;
    blood_pressure: string;
    blood_oxygen: number;
  };
  charts: {
    steps_7d: { date: string; value: number }[];
    heart_rate_24h: { time: string; value: number }[];
    sleep_7d: { date: string; value: number }[];
    blood_pressure_24h: { time: string; systolic: number; diastolic: number }[];
  };
  sync_logs: {
    date: string;
    status: string;
    message: string;
    time: string;
  }[];
};

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    throw new Error(fallback);
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? fallback);
  }
  return response.json();
}

export async function getDeviceOverview(memberId: string): Promise<DeviceOverviewResponse> {
  const response = await fetch(`${API_BASE}/api/devices/${memberId}/overview`);
  return readJson<DeviceOverviewResponse>(response, '获取设备总览失败');
}

export async function syncDevice(memberId: string): Promise<DeviceOverviewResponse> {
  const response = await fetch(`${API_BASE}/api/devices/${memberId}/sync`, {
    method: 'POST'
  });
  return readJson<DeviceOverviewResponse>(response, '同步设备数据失败');
}
