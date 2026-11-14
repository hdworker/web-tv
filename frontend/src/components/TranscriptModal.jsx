import { useEffect, useState } from "react";
import { Drawer, Spin, Typography, Space } from "antd";
import { translations } from "../i18n/ru";
import { videosApi } from "../api";

const { Text } = Typography;

export default function TranscriptModal({ visible, videoId, onClose }) {
  const [transcript, setTranscript] = useState("");
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState("");

  useEffect(() => {
    if (!visible || !videoId) return undefined;

    let cancelled = false;

    const loadTranscript = async () => {
      setLoading(true);
      try {
        const response = await videosApi.getTranscript(videoId);
        if (!cancelled) {
          setTranscript(response.data.transcript || "Транскрипт не найден");
          setSource(response.data.source || "");
        }
      } catch (error) {
        console.error("Error loading transcript:", error);
        if (!cancelled) {
          setTranscript("Ошибка загрузки транскрипта");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadTranscript();
    return () => {
      cancelled = true;
    };
  }, [visible, videoId]);

  return (
    <Drawer
      title={translations.logs.transcript || "Транскрипт"}
      placement="right"
      width={600}
      open={visible}
      onClose={onClose}
    >
      {loading ? (
        <Spin />
      ) : (
        <>
          {source && (
            <Space style={{ marginBottom: 16 }}>
              <Text type="secondary">Источник: </Text>
              <Text code>{source === "database" ? "База данных" : "Страница UN"}</Text>
            </Space>
          )}
          <div
            style={{
              whiteSpace: "pre-wrap",
              maxHeight: "70vh",
              overflowY: "auto",
              padding: "12px",
              background: "#f5f5f5",
              borderRadius: "8px",
              fontFamily: "monospace",
              fontSize: "13px",
              lineHeight: "1.6",
            }}
          >
            {transcript}
          </div>
        </>
      )}
    </Drawer>
  );
}
