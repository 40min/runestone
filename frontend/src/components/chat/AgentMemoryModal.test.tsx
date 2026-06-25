import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest';
import AgentMemoryModal from './AgentMemoryModal';
import * as useMemoryItemsModule from '../../hooks/useMemoryItems';

// Mock the hook
vi.mock('../../hooks/useMemoryItems');

const mockUpdatePriority = vi.fn().mockResolvedValue(undefined);

const mockUseMemoryItems = {
  items: [],
  loading: false,
  error: null,
  hasMore: false,
  fetchItems: vi.fn(),
  createItem: vi.fn(),
  updateItem: vi.fn(),
  updateStatus: vi.fn(),
  updatePriority: mockUpdatePriority,
  deleteItem: vi.fn().mockResolvedValue(undefined),
  clearCategory: vi.fn().mockResolvedValue(undefined),
  checkMaintenanceStatus: vi.fn().mockResolvedValue(false),
};

const setMatchMedia = (matches: boolean) => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches,
      media: '',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
};

describe('AgentMemoryModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    setMatchMedia(false);
    mockUseMemoryItems.checkMaintenanceStatus.mockReset();
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(false);
    (useMemoryItemsModule.default as Mock).mockReturnValue(mockUseMemoryItems);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders correctly when open', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getByText("Teacher's Memory")).toBeInTheDocument();
    expect(screen.getByText('0 items')).toBeInTheDocument();
    expect(screen.getByText('Personal Info')).toBeInTheDocument();
    expect(screen.getByText('Areas to Improve')).toBeInTheDocument();
    expect(screen.queryByText('Knowledge Strengths')).not.toBeInTheDocument();
  });

  it('fetches items on mount when open', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith('personal_info', 'active', true, 'updated_at', 'desc');
  });

  it('keeps personal info requests active-only even though status filters are hidden', async () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.queryByLabelText('Status')).not.toBeInTheDocument();
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith(
      'personal_info',
      'active',
      true,
      'updated_at',
      'desc'
    );
  });

  it('re-fetches memory when maintenance completes after a new chat reset', async () => {
    // Start with maintenance running
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(true);

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    // Sync notice should be displayed immediately
    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();
    // No status check or items fetch should happen synchronously
    expect(mockUseMemoryItems.checkMaintenanceStatus).not.toHaveBeenCalled();
    expect(mockUseMemoryItems.fetchItems).not.toHaveBeenCalled();

    // Advance by 5s to trigger the first status check
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // It should check status, see it is still running, and keep notice without fetching items
    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(1);
    expect(mockUseMemoryItems.fetchItems).not.toHaveBeenCalled();
    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    // Now pretend maintenance completes
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(false);

    // Advance by another 5s
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // It should check status, see it has finished, fetch the items one last time, and clear the notice
    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(2);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Teacher memory is refreshing after the new chat reset.')).not.toBeInTheDocument();
  });

  it('stops polling and clears notice after safety timeout if maintenance hangs', async () => {
    // Keep maintenance running indefinitely
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(true);

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    // Advance timers by 240 seconds (which is the MAX_DURATION_MS)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(240000);
    });

    // The safety timeout should trigger. It fetches items once and clears the notice.
    expect(mockUseMemoryItems.checkMaintenanceStatus.mock.calls.length).toBeLessThanOrEqual(48);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Teacher memory is refreshing after the new chat reset.')).not.toBeInTheDocument();
  });

  it('keeps polling when a maintenance status check fails', async () => {
    mockUseMemoryItems.checkMaintenanceStatus
      .mockRejectedValueOnce(new Error('temporary status failure'))
      .mockResolvedValueOnce(false);

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(1);
    expect(mockUseMemoryItems.fetchItems).not.toHaveBeenCalled();
    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(2);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Teacher memory is refreshing after the new chat reset.')).not.toBeInTheDocument();
  });

  it('falls back to the safety timeout when a maintenance status check never resolves', async () => {
    mockUseMemoryItems.checkMaintenanceStatus.mockImplementation(
      () => new Promise<boolean>(() => {})
    );

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(244000);
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus.mock.calls.length).toBeGreaterThan(1);
    expect(mockUseMemoryItems.checkMaintenanceStatus.mock.calls.length).toBeLessThan(30);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Teacher memory is refreshing after the new chat reset.')).not.toBeInTheDocument();
  });

  it('does not cancel the status checks when tab is switched during the refresh window', async () => {
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(true);

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    // Switch tab/category to 'Areas to Improve'
    const areasTab = screen.getByText('Areas to Improve');
    await act(async () => {
      fireEvent.click(areasTab);
    });

    // Switch tab should trigger fetchItems for the new category immediately
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalled();
    mockUseMemoryItems.fetchItems.mockClear();

    // Now advance timers to check if the status check loop is still running
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    // Resolve maintenance
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(false);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // The notice should disappear, and fetchItems should be called one final time
    expect(screen.queryByText('Teacher memory is refreshing after the new chat reset.')).not.toBeInTheDocument();
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledTimes(1);
  });

  it('does not let an older refresh cycle clear the notice for a newer reset', async () => {
    let resolvePendingRefresh: (() => void) | null = null;
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(false);

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolvePendingRefresh = resolve;
        })
    );
    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(true);
    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={2} />);

    await act(async () => {
      resolvePendingRefresh?.();
      await Promise.resolve();
    });

    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();
  });

  it('resumes maintenance polling after closing and reopening the modal', async () => {
    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(true);

    const { rerender } = render(
      <AgentMemoryModal open={true} onClose={() => {}} refreshToken={0} />
    );

    mockUseMemoryItems.fetchItems.mockClear();
    mockUseMemoryItems.checkMaintenanceStatus.mockClear();

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    rerender(<AgentMemoryModal open={false} onClose={() => {}} refreshToken={1} />);
    expect(screen.queryByText('Teacher memory is refreshing after the new chat reset.')).not.toBeInTheDocument();

    mockUseMemoryItems.checkMaintenanceStatus.mockResolvedValue(false);
    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);

    expect(screen.getByText('Teacher memory is refreshing after the new chat reset.')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(2);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledTimes(2);

    rerender(<AgentMemoryModal open={true} onClose={() => {}} refreshToken={1} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockUseMemoryItems.checkMaintenanceStatus).toHaveBeenCalledTimes(2);
  });

  it('changes category when tab is clicked', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const areasTab = screen.getByText('Areas to Improve');
    fireEvent.click(areasTab);

    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith('area_to_improve', undefined, true, 'updated_at', 'desc');
  });

  it('keeps updated_at desc default on Areas to Improve tab', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('Areas to Improve'));
    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith('area_to_improve', undefined, true, 'updated_at', 'desc');
  });

  it('allows selecting Priority + Ascending sort on Areas to Improve tab', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('Areas to Improve'));

    const sortBySelect = document.querySelector('[aria-labelledby="sort-by-label"]') as HTMLElement;
    fireEvent.mouseDown(sortBySelect);
    fireEvent.click(screen.getByText('Priority'));

    const directionSelect = document.querySelector('[aria-labelledby="sort-direction-label"]') as HTMLElement;
    fireEvent.mouseDown(directionSelect);
    fireEvent.click(screen.getByText('Ascending'));

    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith('area_to_improve', undefined, true, 'priority', 'asc');
  });

  it('resets sort to updated_at desc and hides Priority option when leaving Areas to Improve', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('Areas to Improve'));

    const sortBySelect = document.querySelector('[aria-labelledby="sort-by-label"]') as HTMLElement;
    fireEvent.mouseDown(sortBySelect);
    fireEvent.click(screen.getByText('Priority'));

    fireEvent.click(screen.getByText('Personal Info'));
    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith('personal_info', 'active', true, 'updated_at', 'desc');

    const personalSortBySelect = document.querySelector('[aria-labelledby="sort-by-label"]') as HTMLElement;
    fireEvent.mouseDown(personalSortBySelect);
    expect(screen.queryByText('Priority')).not.toBeInTheDocument();
  });

  it('opens add form when "Add Item" is clicked', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const addButton = screen.getByText('Add Item');
    fireEvent.click(addButton);

    expect(screen.getByText('Add Memory Item')).toBeInTheDocument();
    expect(screen.getByLabelText(/Key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Content/i)).toBeInTheDocument();
  });

  it('collapses mobile filters behind a toggle', () => {
    setMatchMedia(true);

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getByRole('button', { name: 'Filters' })).toBeInTheDocument();
    expect(screen.queryByText('All statuses')).not.toBeInTheDocument();
    expect(screen.getAllByText('Newest first').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'Filters' }));
    expect(screen.getByText('Clear Category')).toBeVisible();
  });

  it('shows category-specific status options in add form for area_to_improve', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Areas to Improve'));
    fireEvent.click(screen.getByText('Add Item'));

    const formStatusSelect = document.querySelector(
      '[aria-labelledby="form-status-label"]'
    ) as HTMLElement;
    fireEvent.mouseDown(formStatusSelect);
    expect(screen.getByText('Struggling')).toBeInTheDocument();
    expect(screen.getByText('Improving')).toBeInTheDocument();
    expect(screen.getByText('Mastered')).toBeInTheDocument();
    expect(screen.queryByText('Outdated')).not.toBeInTheDocument();
  });

  it('does not offer Active status for area_to_improve in add form', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Areas to Improve'));
    fireEvent.click(screen.getByText('Add Item'));

    const formStatusSelect = document.querySelector(
      '[aria-labelledby="form-status-label"]'
    ) as HTMLElement;
    fireEvent.mouseDown(formStatusSelect);
    expect(screen.queryByText('Active')).not.toBeInTheDocument();
  });

  it('displays items in cards', () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getAllByText('test-key').length).toBeGreaterThan(0);
    expect(screen.getByText('test-content')).toBeInTheDocument();
    expect(screen.queryByText('Active')).not.toBeInTheDocument();
    expect(screen.getByText('1 item')).toBeInTheDocument();
  });

  it('shows category helper text for areas to improve', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Areas to Improve'));

    expect(
      screen.getByText("These are areas where you've shown difficulty. Focus on them to improve faster!")
    ).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Priority badge tests
  // ---------------------------------------------------------------------------

  it('shows priority badge for area_to_improve item with priority set', () => {
    const mockItems = [
      {
        id: 1,
        key: 'verb-tense',
        content: 'Struggles with verb tense',
        category: 'area_to_improve',
        status: 'struggling',
        priority: 2,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(screen.getByLabelText('Priority badge')).toBeInTheDocument();
    expect(screen.getByLabelText('Priority badge')).toHaveTextContent('P2');
  });

  it('shows P– badge for area_to_improve item without priority', () => {
    const mockItems = [
      {
        id: 1,
        key: 'pronunciation',
        content: 'Pronunciation issues',
        category: 'area_to_improve',
        status: 'struggling',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(screen.getByLabelText('Priority badge')).toHaveTextContent('P–');
  });

  it('does not show priority badge for personal_info items', () => {
    const mockItems = [
      {
        id: 1,
        key: 'name',
        content: 'Alice',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(screen.queryByLabelText('Priority badge')).not.toBeInTheDocument();
  });

  it('clicking priority badge shows inline priority selector', () => {
    const mockItems = [
      {
        id: 1,
        key: 'verb-tense',
        content: 'Struggles with verb tense',
        category: 'area_to_improve',
        status: 'struggling',
        priority: 2,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Priority badge'));
    expect(screen.getByLabelText('Priority selector')).toBeInTheDocument();
  });

  it('shows priority field in add form when category is area_to_improve', async () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    // Switch to area_to_improve tab
    fireEvent.click(screen.getByText('Areas to Improve'));
    fireEvent.click(screen.getByText('Add Item'));

    expect(screen.getByLabelText(/Priority/i)).toBeInTheDocument();
  });

  it('does not show priority field in add form for personal_info', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    // personal_info is the default tab
    fireEvent.click(screen.getByText('Add Item'));

    expect(screen.queryByLabelText(/Status/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Priority/i)).not.toBeInTheDocument();
  });

  it('updates personal_info through the generic update-by-id path', async () => {
    const mockItems = [
      {
        id: 1,
        key: 'goal',
        content: 'Practice speaking',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      },
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Edit item'));
    fireEvent.change(screen.getByLabelText(/Content/i), { target: { value: 'Practice reading' } });

    await act(async () => {
      fireEvent.click(screen.getByText('Save'));
    });

    expect(mockUseMemoryItems.updateItem).toHaveBeenCalledWith(1, {
      key: 'goal',
      content: 'Practice reading',
      status: undefined,
      priority: undefined,
    });
    expect(mockUseMemoryItems.createItem).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // Existing tests
  // ---------------------------------------------------------------------------

  it('shows inline clear confirmation and calls clearCategory on confirm', async () => {
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: [{ id: 1 }], // Ensure button is enabled
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Clear Category'));
    expect(screen.getByText('Confirm Clear')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByText('Confirm Clear'));
    });
    expect(mockUseMemoryItems.clearCategory).toHaveBeenCalledWith('personal_info');
  });

  it('cancels inline clear confirmation', () => {
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: [{ id: 1 }],
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Clear Category'));
    fireEvent.click(screen.getByText('Cancel'));

    expect(screen.getByText('Clear Category')).toBeInTheDocument();
    expect(screen.queryByText('Confirm Clear')).not.toBeInTheDocument();
  });

  it('shows inline delete confirmation and cancels', () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Delete item'));
    expect(screen.getByLabelText('Confirm delete')).toBeInTheDocument();
    expect(screen.getByLabelText('Cancel delete')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Cancel delete'));
    expect(screen.getByLabelText('Delete item')).toBeInTheDocument();
  });

  it('confirms delete and calls deleteItem', async () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Delete item'));
    await act(async () => {
      fireEvent.click(screen.getByLabelText('Confirm delete'));
    });

    expect(mockUseMemoryItems.deleteItem).toHaveBeenCalledWith(1);
  });

  it('refreshes the list when delete fails because the item went stale', async () => {
    const mockDeleteItem = vi.fn().mockRejectedValueOnce(new Error('Memory item with id 1 not found'));
    const mockItems = [
      {
        id: 1,
        key: 'verb-tense',
        content: 'Struggles with verb tense',
        category: 'area_to_improve',
        status: 'struggling',
        priority: 2,
        updated_at: new Date().toISOString(),
      },
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
      deleteItem: mockDeleteItem,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    await act(async () => {
      fireEvent.click(screen.getByLabelText('Delete item'));
    });

    await act(async () => {
      fireEvent.click(screen.getByLabelText('Confirm delete'));
    });

    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith(
      'personal_info',
      'active',
      true,
      'updated_at',
      'desc'
    );
    expect(
      screen.getByText('That memory item changed during background cleanup. Refreshed the list.')
    ).toBeInTheDocument();
  });
});
