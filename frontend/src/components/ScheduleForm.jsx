import { DatePicker, Button, Card, Space, message } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { scheduleApi } from "../api";
import { translations } from "../i18n/ru";
import { useState } from "react";

const { RangePicker } = DatePicker;

export default function ScheduleForm({ onLoadComplete }) {
  const [dates, setDates] = useState(null);
  const handleLoad = async (datesArg) => {
    const d = datesArg || dates;
    if (!d || d.length < 2) {
      message.error("Выберите период");
      return;
    }

    const startDate = d[0].format("YYYY-MM-DD");
    const endDate = d[1].format("YYYY-MM-DD");

    try {
      message.loading({ content: translations.schedule.loading, key: "load" });
      
      const response = await scheduleApi.saveToDb(startDate, endDate);
      
      message.success({
        content: `${translations.messages.saved} ${response.data.saved} ${translations.messages.items}`,
        key: "load",
      });
      
      if (onLoadComplete) {
        onLoadComplete();
      }
    } catch (error) {
      console.error("[ERROR] Schedule Load failed:", error);
      message.error({
        content: error.response?.data?.detail || "Ошибка загрузки",
        key: "load",
      });
    }
  };

  return (
    <Card title={translations.schedule.title} style={{ marginBottom: 24 }}>
      <Space wrap>
        <RangePicker
          format="YYYY-MM-DD"
          placeholder={[
            translations.schedule.startDate,
            translations.schedule.endDate,
          ]}
          onChange={(val) => setDates(val)}
          allowClear
        />
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          onClick={() => handleLoad()}
        >
          {translations.schedule.loadButton}
        </Button>
      </Space>
    </Card>
  );
}
