import React, { useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";
import BarChartIcon from "@mui/icons-material/BarChart";
import AddIcon from "@mui/icons-material/Add";
import { useRecentVocabulary, useVocabularyStats } from "../hooks/useVocabulary";
import { CustomButton, ErrorAlert, LoadingSpinner } from "./ui";
import AddEditVocabularyModal from "./AddEditVocabularyModal";
import VocabularyStatsModal from "./VocabularyStatsModal";
import VocabularyOverview from "./vocabulary/VocabularyOverview";
import VocabularyLedger from "./vocabulary/VocabularyLedger";

const VocabularyView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSearchTerm, setActiveSearchTerm] = useState("");
  const [preciseSearch, setPreciseSearch] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [boostingItemIds, setBoostingItemIds] = useState<Set<number>>(new Set());
  const [boostError, setBoostError] = useState<string | null>(null);
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const boostingItemIdsRef = useRef<Set<number>>(new Set());
  const loadMoreSentinelRef = useRef<HTMLDivElement | null>(null);

  const {
    stats,
    loading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useVocabularyStats();
  const {
    recentVocabulary,
    loading,
    error,
    loadingMore,
    hasMore,
    loadMore,
    isEditModalOpen,
    editingItem,
    openEditModal,
    closeEditModal,
    updateVocabularyItem,
    createVocabularyItem,
    deleteVocabularyItem,
    lookupVocabularyItem,
  } = useRecentVocabulary(activeSearchTerm, preciseSearch);

  useEffect(() => {
    if (!loading && isInitialLoad) {
      setIsInitialLoad(false);
    }
  }, [loading, isInitialLoad]);

  useEffect(() => {
    if (searchTerm.length > 3) {
      setActiveSearchTerm(searchTerm);
    } else if (searchTerm.length === 0) {
      setActiveSearchTerm("");
    }
  }, [searchTerm]);

  useEffect(() => {
    const sentinel = loadMoreSentinelRef.current;
    if (!sentinel || !hasMore || loading || loadingMore) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void loadMore();
        }
      },
      { rootMargin: "240px 0px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, loadMore]);

  const handleSaveEdit = async (
    updatedItem: Partial<(typeof recentVocabulary)[0]>
  ) => {
    if (editingItem) {
      await updateVocabularyItem(editingItem.id, updatedItem);
    } else {
      await createVocabularyItem(updatedItem);
    }
    await refetchStats();
  };

  const handleDelete = async () => {
    if (!editingItem) return;
    await deleteVocabularyItem(editingItem.id);
    await refetchStats();
  };

  const handleBoostPriority = async (
    event: React.MouseEvent,
    item: (typeof recentVocabulary)[0]
  ) => {
    event.stopPropagation();
    setBoostError(null);

    const nextPriority = Math.max(item.priority_learn - 1, 0);
    if (nextPriority === item.priority_learn) return;
    if (boostingItemIdsRef.current.has(item.id)) return;

    boostingItemIdsRef.current.add(item.id);
    setBoostingItemIds(new Set(boostingItemIdsRef.current));

    try {
      await updateVocabularyItem(item.id, { priority_learn: nextPriority });
      await refetchStats();
    } catch (updateError) {
      const message =
        updateError instanceof Error ? updateError.message : "Unknown error";
      setBoostError(`Failed to boost priority: ${message}`);
    } finally {
      boostingItemIdsRef.current.delete(item.id);
      setBoostingItemIds(new Set(boostingItemIdsRef.current));
    }
  };

  if (loading && isInitialLoad) return <LoadingSpinner />;
  if (error && recentVocabulary.length === 0) return <ErrorAlert message={error} />;

  return (
    <Box sx={{ py: { xs: 2, sm: 4 }, display: "flex", flexDirection: "column", gap: 2.25 }}>
      <Box
        component="header"
        sx={{
          display: "flex",
          alignItems: { xs: "flex-start", md: "flex-end" },
          justifyContent: "space-between",
          flexDirection: { xs: "column", md: "row" },
          gap: 2.5,
          pb: 1,
        }}
      >
        <Box>
          <Typography
            sx={{
              color: "#38e07b",
              fontSize: "0.72rem",
              fontWeight: 700,
              letterSpacing: "0.13em",
              textTransform: "uppercase",
              mb: 1,
            }}
          >
            Your Swedish study library
          </Typography>
          <Typography
            component="h1"
            sx={{
              color: "#f3f6ff",
              fontSize: { xs: "2.5rem", sm: "3.25rem" },
              fontWeight: 700,
              letterSpacing: "-0.055em",
              lineHeight: 1,
            }}
          >
            Vocabulary
          </Typography>
          <Typography
            sx={{ color: "#bdc9e5", fontSize: { xs: "0.95rem", sm: "1.05rem" }, mt: 1.45 }}
          >
            Find, refine, and prioritise the words you want to remember.
          </Typography>
        </Box>

        <Box sx={{ display: "flex", gap: 1.25, width: { xs: "100%", md: "auto" } }}>
          <CustomButton
            variant="secondary"
            startIcon={<BarChartIcon fontSize="small" />}
            aria-label="Open vocabulary statistics"
            onClick={() => setStatsModalOpen(true)}
            sx={{
              flex: { xs: 1, md: "none" },
              color: "#e3e9fb",
              border: "1px solid rgba(99, 114, 173, 0.45)",
              backgroundColor: "rgba(9, 15, 51, 0.55)",
            }}
          >
            Statistics
          </CustomButton>
          <CustomButton
            variant="primary"
            startIcon={<AddIcon fontSize="small" />}
            onClick={() => openEditModal(null)}
            sx={{ flex: { xs: 1, md: "none" } }}
          >
            Add word
          </CustomButton>
        </Box>
      </Box>

      {statsError ? (
        <ErrorAlert message={statsError} />
      ) : (
        <VocabularyOverview stats={stats} loading={statsLoading} />
      )}

      {boostError && (
        <Typography role="alert" sx={{ color: "#fda4af", fontSize: "0.82rem" }}>
          {boostError}
        </Typography>
      )}

      <VocabularyLedger
        items={recentVocabulary}
        searchTerm={searchTerm}
        hasActiveSearch={Boolean(activeSearchTerm)}
        preciseSearch={preciseSearch}
        loading={loading && !isInitialLoad}
        loadingMore={loadingMore}
        hasMore={hasMore}
        error={error}
        boostingItemIds={boostingItemIds}
        loadMoreSentinelRef={loadMoreSentinelRef}
        onSearchTermChange={setSearchTerm}
        onSearch={() => setActiveSearchTerm(searchTerm)}
        onClearSearch={() => {
          setSearchTerm("");
          setActiveSearchTerm("");
        }}
        onPreciseSearchChange={setPreciseSearch}
        onItemClick={openEditModal}
        onBoostPriority={(event, item) => void handleBoostPriority(event, item)}
      />

      <AddEditVocabularyModal
        open={isEditModalOpen}
        item={editingItem}
        onClose={closeEditModal}
        onSave={handleSaveEdit}
        onDelete={handleDelete}
        onLookup={lookupVocabularyItem}
        onLookupFound={openEditModal}
      />
      <VocabularyStatsModal
        open={statsModalOpen}
        onClose={() => setStatsModalOpen(false)}
      />
    </Box>
  );
};

export default VocabularyView;
