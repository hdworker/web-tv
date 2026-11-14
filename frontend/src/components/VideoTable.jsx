import { Table, Button, Space, Tag, Tooltip, Typography } from "antd";
import {
  DownloadOutlined,
  AudioOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
  StopOutlined,
  FolderOpenOutlined,
} from "@ant-design/icons";
import { translations } from "../i18n/ru";
import { videosApi } from "../api";
import LogModal from "./LogModal";
import TranscriptModal from "./TranscriptModal";
import { useState, useEffect } from "react";

const { Text } = Typography;

const statusColors = {
  new: "blue",
  downloaded: "green",
  partial: "orange",
  transcribed: "purple",
  failed: "red",
};

export default function VideoTable({ videos, loading, onRefresh }) {
  const [logModalVisible, setLogModalVisible] = useState(false);
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [downloadingIds, setDownloadingIds] = useState(new Set());
  const [segmentsInfo, setSegmentsInfo] = useState({});
  const [transcriptModalVisible, setTranscriptModalVisible] = useState(false);

  useEffect(() => {
    const loadMissingSegments = async () => {
      for (const video of videos) {
        if (video.status === "partial" && !segmentsInfo[video.id]) {
          try {
            const response = await videosApi.getSegmentsInfo(video.id);
            setSegmentsInfo(prev => ({ ...prev, [video.id]: response.data }));
          } catch (error) {
            console.error("Error loading segments info:", error);
          }
        }
      }
    };

    loadMissingSegments();
  }, [videos, segmentsInfo]);

  const handleDownload = async (id) => {
    try {
      setDownloadingIds(prev => new Set([...prev, id]));
      await videosApi.download(id);
      setSelectedVideoId(id);
      setLogModalVisible(true);
    } catch (error) {
      console.error("Download error:", error);
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleStop = async (id) => {
    try {
      await videosApi.stopDownload(id);
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      if (onRefresh) onRefresh();
    } catch (error) {
      console.error("Stop error:", error);
    }
  };

  const handleConcat = async (id) => {
    try {
      setSelectedVideoId(id);
      setLogModalVisible(true);
      await videosApi.concat(id);
      if (onRefresh) onRefresh();
    } catch (error) {
      console.error("Concat error:", error);
    }
  };

  const handleTranscribe = async (id) => {
    try {
      await videosApi.transcribe(id);
      setSelectedVideoId(id);
      setLogModalVisible(true);
    } catch (error) {
      console.error("Transcribe error:", error);
    }
  };

  const handleGetDetails = async (id) => {
    try {
      await videosApi.getDetails(id);
      if (onRefresh) onRefresh();
    } catch (error) {
      console.error("Details error:", error);
    }
  };

  const handleShowLogs = (id) => {
    setSelectedVideoId(id);
    setLogModalVisible(true);
  };

  const handleShowTranscript = (id) => {
    setSelectedVideoId(id);
    setTranscriptModalVisible(true);
  };

  const handleOpenFolder = async (id) => {
    try {
      await videosApi.openFolder(id);
    } catch (error) {
      console.error("Open folder error:", error);
    }
  };

  const handlePlay = (id) => {
    window.open(videosApi.streamUrl(id), "_blank");
  };

  const columns = [
    {
      title: translations.table.time,
      dataIndex: "date",
      key: "date",
      width: 100,
    },
    {
      title: translations.table.category,
      dataIndex: "category",
      key: "category",
      width: 180,
      render: (cat) => cat || "-",
    },
    {
      title: translations.table.title,
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (title, record) => (
        <a href={record.url} target="_blank" rel="noopener noreferrer">
          {title}
        </a>
      ),
    },
    {
      title: translations.table.description,
      dataIndex: "description",
      key: "description",
      width: 250,
      ellipsis: true,
      render: (desc) => (
        <Tooltip title={desc}>{desc || "-"}</Tooltip>
      ),
    },
    {
      title: translations.table.duration,
      dataIndex: "duration",
      key: "duration",
      width: 100,
    },
    {
      title: translations.table.status,
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status, record) => (
        <Space direction="vertical" size={0}>
          <Tag color={statusColors[status] || "default"}>
            {translations.status[status] || status}
          </Tag>
          {status === "partial" && segmentsInfo[record.id] && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              до {segmentsInfo[record.id].last_segment} сегм.
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: translations.table.file,
      key: "file",
      width: 100,
      render: (_, record) => {
        const info = segmentsInfo[record.id];
        if (!info) return "-";
        if (info.has_output) return "✓ output";
        if (info.last_segment > 0) return `${info.last_segment} сегм.`;
        return "-";
      },
    },
    {
      title: translations.table.actions,
      key: "actions",
      width: 280,
      render: (_, record) => (
        <Space size="small">
          {/* Кнопка Скачать или Остановить */}
          {downloadingIds.has(record.id) ? (
            <Tooltip title={translations.actions.stop}>
              <Button
                danger
                size="small"
                icon={<StopOutlined />}
                onClick={() => handleStop(record.id)}
              />
            </Tooltip>
          ) : (
            <Tooltip title={translations.actions.download}>
              <Button
                type="primary"
                size="small"
                icon={<DownloadOutlined />}
                onClick={() => handleDownload(record.id)}
                disabled={record.status === "downloaded"}
              />
            </Tooltip>
          )}
          
          {/* Кнопка Склеить (для partial) */}
          {record.status === "partial" && (
            <Tooltip title={translations.actions.concat}>
              <Button
                size="small"
                onClick={() => handleConcat(record.id)}
              >
                {translations.actions.concat}
              </Button>
            </Tooltip>
          )}
          
          {/* Кнопка Проиграть (для downloaded и partial) */}
          {(record.status === "downloaded" || record.status === "partial") && record.local_video_path && (
            <Tooltip title={translations.actions.play}>
              <Button
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={() => handlePlay(record.id)}
              />
            </Tooltip>
          )}
          
          {/* Кнопка Открыть папку */}
          {record.local_video_path && (
            <Tooltip title={translations.actions.openFolder}>
              <Button
                size="small"
                icon={<FolderOpenOutlined />}
                onClick={() => handleOpenFolder(record.id)}
              />
            </Tooltip>
          )}
          
          <Tooltip title={translations.actions.transcribe}>
            <Button
              size="small"
              icon={<AudioOutlined />}
              onClick={() => handleTranscribe(record.id)}
              disabled={record.status !== "downloaded" && record.status !== "partial"}
            />
          </Tooltip>
          <Tooltip title="Транскрипт">
            <Button
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => handleShowTranscript(record.id)}
            />
          </Tooltip>
          <Tooltip title={translations.actions.details}>
            <Button
              size="small"
              icon={<InfoCircleOutlined />}
              onClick={() => handleGetDetails(record.id)}
            />
          </Tooltip>
          <Tooltip title={translations.actions.viewLogs}>
            <Button
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => handleShowLogs(record.id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Table
        columns={columns}
        dataSource={videos}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1400 }}
      />
      {selectedVideoId && (
        <LogModal
          visible={logModalVisible}
          videoId={selectedVideoId}
          onClose={() => setLogModalVisible(false)}
        />
      )}
      {selectedVideoId && (
        <TranscriptModal
          visible={transcriptModalVisible}
          videoId={selectedVideoId}
          onClose={() => setTranscriptModalVisible(false)}
        />
      )}
    </>
  );
}
