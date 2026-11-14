import { useEffect, useState } from "react";
import { Drawer, Timeline, Typography } from "antd";
import { translations } from "../i18n/ru";
import { videosApi } from "../api";

const { Text } = Typography;

const statusColors = {
  running: "blue",
  completed: "green",
  failed: "red",
  pending: "default",
};

export default function LogModal({ visible, videoId, onClose }) {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    if (!visible || !videoId) return undefined;

    const loadLogs = async () => {
      try {
        const response = await videosApi.getLogs(videoId);
        setLogs(response.data);
      } catch (error) {
        console.error("Error loading logs:", error);
      }
    };

    loadLogs();
    const interval = setInterval(loadLogs, 1000);
    return () => clearInterval(interval);
  }, [visible, videoId]);

  return (
    <Drawer
      title={translations.logs.title}
      placement="right"
      width={500}
      open={visible}
      onClose={onClose}
    >
      {logs.length === 0 ? (
        <Text type="secondary">{translations.logs.noLogs}</Text>
      ) : (
        <Timeline
          mode="left"
          items={logs.slice().reverse().map((log) => ({
            color: statusColors[log.status] || "gray",
            children: (
              <>
                <Text strong>{log.action}</Text>
                <br />
                <Text code style={{ display: "block", whiteSpace: "pre-wrap" }}>
                  {log.log_text}
                </Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {log.created_at}
                </Text>
              </>
            ),
          }))}
        />
      )}
    </Drawer>
  );
}
