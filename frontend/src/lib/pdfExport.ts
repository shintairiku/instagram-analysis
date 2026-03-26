import jsPDF from 'jspdf';
import autoTable, { type UserOptions } from 'jspdf-autotable';
import html2canvas from 'html2canvas';

// ====================================================================
// Brand Colors & Layout Constants
// ====================================================================
const COLORS = {
  primary: [192, 180, 135] as [number, number, number],    // #c0b487 - header
  accent: [243, 165, 34] as [number, number, number],      // #f3a522 - primary accent
  dark: [45, 45, 45] as [number, number, number],           // #2d2d2d - text
  medium: [102, 102, 102] as [number, number, number],      // #666666 - secondary text
  light: [153, 153, 153] as [number, number, number],       // #999999 - muted text
  tableHeader: [192, 180, 135] as [number, number, number], // #c0b487
  tableHeaderText: [255, 255, 255] as [number, number, number],
  tableAlt: [249, 247, 242] as [number, number, number],    // #f9f7f2
  tableBorder: [224, 224, 224] as [number, number, number], // #e0e0e0
  white: [255, 255, 255] as [number, number, number],
  green: [34, 139, 34] as [number, number, number],
  red: [220, 53, 69] as [number, number, number],
};

const PAGE = {
  width: 210,
  height: 297,
  margin: { top: 25, bottom: 20, left: 15, right: 15 },
};

const CONTENT_WIDTH = PAGE.width - PAGE.margin.left - PAGE.margin.right;
const HEADER_HEIGHT = 12;
const FOOTER_HEIGHT = 10;
const STORAGE_KEYS = {
  SELECTED_ACCOUNT: 'instagram_analysis_selected_account',
  ACCOUNTS_CACHE: 'instagram_analysis_accounts_cache',
} as const;

type PdfAccountInfo = {
  coverName: string;
  coverIdLine: string;
  fileNameBase: string;
};

// ====================================================================
// Font Loading (Lazy - caches base64 data, registers per doc instance)
// ====================================================================
let cachedRegularFont: string | null = null;
let cachedBoldFont: string | null = null;

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

async function fetchFontBase64(url: string): Promise<string> {
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  return arrayBufferToBase64(arrayBuffer);
}

function registerFont(doc: jsPDF, base64: string, fontName: string, style: string): void {
  const fileName = `${fontName}-${style}.ttf`;
  doc.addFileToVFS(fileName, base64);
  doc.addFont(fileName, fontName, style);
}

async function ensureFonts(doc: jsPDF): Promise<void> {
  // Fetch font data (cached after first load)
  if (!cachedRegularFont) {
    cachedRegularFont = await fetchFontBase64('/fonts/NotoSansJP-Regular.ttf');
  }
  if (!cachedBoldFont) {
    cachedBoldFont = await fetchFontBase64('/fonts/NotoSansJP-Bold.ttf');
  }

  // Register fonts with this document instance
  registerFont(doc, cachedRegularFont, 'NotoSansJP', 'normal');
  registerFont(doc, cachedBoldFont, 'NotoSansJP', 'bold');
  doc.setFont('NotoSansJP', 'normal');
}

// ====================================================================
// Helper Utilities
// ====================================================================
function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}/${m}/${d}`;
}

function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '---';
  return num.toLocaleString();
}

function ensureHonorific(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return 'Instagram Account 様';
  return `${trimmed.replace(/\s*様$/, '')} 様`;
}

// ====================================================================
// Page Header & Footer
// ====================================================================
function drawPageHeader(doc: jsPDF, title: string): void {
  // Accent bar at top
  doc.setFillColor(...COLORS.primary);
  doc.rect(0, 0, PAGE.width, 5, 'F');

  // Report title in header
  doc.setFont('NotoSansJP', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...COLORS.light);
  doc.text(title, PAGE.margin.left, 12);

  // Thin separator line
  doc.setDrawColor(...COLORS.tableBorder);
  doc.setLineWidth(0.3);
  doc.line(PAGE.margin.left, HEADER_HEIGHT + 3, PAGE.width - PAGE.margin.right, HEADER_HEIGHT + 3);
}

function drawPageFooter(doc: jsPDF, pageNum: number, totalPages: number): void {
  const y = PAGE.height - PAGE.margin.bottom + 5;

  // Separator line
  doc.setDrawColor(...COLORS.tableBorder);
  doc.setLineWidth(0.3);
  doc.line(PAGE.margin.left, y - 3, PAGE.width - PAGE.margin.right, y - 3);

  // Page number (right)
  doc.setFont('NotoSansJP', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...COLORS.light);
  doc.text(
    `${pageNum} / ${totalPages}`,
    PAGE.width - PAGE.margin.right,
    y + 2,
    { align: 'right' }
  );

  // Generation date (left)
  doc.text(
    `Generated: ${formatDate(new Date())}`,
    PAGE.margin.left,
    y + 2
  );
}

function addPageWithHeader(doc: jsPDF, title: string): void {
  doc.addPage();
  drawPageHeader(doc, title);
}

// ====================================================================
// Cover Page
// ====================================================================
function drawCoverPage(
  doc: jsPDF,
  reportType: string,
  accountName: string,
  accountIdLine: string,
  subtitle: string,
  meta?: { dateRange?: string; totalPosts?: number }
): void {
  // Large accent bar
  doc.setFillColor(...COLORS.primary);
  doc.rect(0, 0, PAGE.width, 80, 'F');

  // Decorative accent stripe
  doc.setFillColor(...COLORS.accent);
  doc.rect(0, 76, PAGE.width, 4, 'F');

  // Report Title
  doc.setFont('NotoSansJP', 'bold');
  doc.setFontSize(28);
  doc.setTextColor(...COLORS.white);
  doc.text('Instagram', PAGE.width / 2, 35, { align: 'center' });
  doc.setFontSize(22);
  doc.text('分析レポート', PAGE.width / 2, 50, { align: 'center' });

  // Report type badge
  doc.setFontSize(13);
  doc.setTextColor(255, 255, 255);
  doc.text(reportType, PAGE.width / 2, 67, { align: 'center' });

  // Account info section
  let yPos = 105;
  const centeredTextWidth = CONTENT_WIDTH - 20;
  const accountNameLines = doc.splitTextToSize(accountName, centeredTextWidth);
  const accountIdLines = doc.splitTextToSize(accountIdLine, centeredTextWidth);
  const subtitleLines = doc.splitTextToSize(subtitle, centeredTextWidth);

  doc.setFont('NotoSansJP', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...COLORS.dark);
  doc.text(accountNameLines, PAGE.width / 2, yPos, { align: 'center' });
  yPos += accountNameLines.length * 7;

  doc.setFont('NotoSansJP', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...COLORS.medium);
  doc.text(accountIdLines, PAGE.width / 2, yPos, { align: 'center' });
  yPos += accountIdLines.length * 5 + 5;

  doc.setFontSize(11);
  doc.setTextColor(...COLORS.medium);
  doc.text(subtitleLines, PAGE.width / 2, yPos, { align: 'center' });
  yPos += subtitleLines.length * 6 + 8;

  // Meta info
  if (meta?.dateRange) {
    doc.setFontSize(10);
    doc.setTextColor(...COLORS.medium);
    doc.text(`対象期間: ${meta.dateRange}`, PAGE.width / 2, yPos, { align: 'center' });
    yPos += 8;
  }

  if (meta?.totalPosts !== undefined) {
    doc.text(`対象投稿数: ${meta.totalPosts}件`, PAGE.width / 2, yPos, { align: 'center' });
    yPos += 8;
  }

  // Generation date
  yPos += 10;
  doc.setFontSize(9);
  doc.setTextColor(...COLORS.light);
  doc.text(`レポート生成日: ${formatDate(new Date())}`, PAGE.width / 2, yPos, { align: 'center' });

  // Bottom decoration
  doc.setFillColor(...COLORS.primary);
  doc.rect(0, PAGE.height - 12, PAGE.width, 12, 'F');
  doc.setFillColor(...COLORS.accent);
  doc.rect(0, PAGE.height - 12, PAGE.width, 2, 'F');

  // Confidential notice
  doc.setFont('NotoSansJP', 'normal');
  doc.setFontSize(7);
  doc.setTextColor(...COLORS.white);
  doc.text('Confidential - 本レポートは機密情報を含みます', PAGE.width / 2, PAGE.height - 4, { align: 'center' });
}

// ====================================================================
// Summary Cards Section
// ====================================================================
function drawSummaryCards(
  doc: jsPDF,
  cards: Array<{ label: string; value: string; sub?: string }>,
  startY: number
): number {
  const cardWidth = (CONTENT_WIDTH - 12) / 3; // 3 columns with gaps
  const cardHeight = 28;
  const gap = 6;

  cards.forEach((card, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = PAGE.margin.left + col * (cardWidth + gap);
    const y = startY + row * (cardHeight + gap);

    // Card background
    doc.setFillColor(249, 249, 249);
    doc.roundedRect(x, y, cardWidth, cardHeight, 2, 2, 'F');

    // Accent left border
    doc.setFillColor(...COLORS.accent);
    doc.rect(x, y, 2, cardHeight, 'F');

    // Label
    doc.setFont('NotoSansJP', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...COLORS.medium);
    doc.text(card.label, x + 6, y + 9);

    // Value
    doc.setFont('NotoSansJP', 'bold');
    doc.setFontSize(14);
    doc.setTextColor(...COLORS.dark);
    doc.text(card.value, x + 6, y + 20);

    // Sub text
    if (card.sub) {
      doc.setFont('NotoSansJP', 'normal');
      doc.setFontSize(7);
      doc.setTextColor(...COLORS.light);
      doc.text(card.sub, x + 6, y + 25);
    }
  });

  const totalRows = Math.ceil(cards.length / 3);
  return startY + totalRows * (cardHeight + gap) + 5;
}

// ====================================================================
// Section Title
// ====================================================================
function drawSectionTitle(doc: jsPDF, title: string, y: number): number {
  doc.setFont('NotoSansJP', 'bold');
  doc.setFontSize(13);
  doc.setTextColor(...COLORS.dark);
  doc.text(title, PAGE.margin.left, y);

  // Underline with accent
  doc.setDrawColor(...COLORS.accent);
  doc.setLineWidth(0.8);
  doc.line(PAGE.margin.left, y + 2, PAGE.margin.left + 40, y + 2);

  return y + 10;
}

// ====================================================================
// AutoTable Default Styles
// ====================================================================
function getAutoTableDefaults(): Partial<UserOptions> {
  return {
    styles: {
      font: 'NotoSansJP',
      fontSize: 7.5,
      cellPadding: 2.5,
      textColor: COLORS.dark,
      lineColor: COLORS.tableBorder,
      lineWidth: 0.2,
    },
    headStyles: {
      fillColor: COLORS.tableHeader,
      textColor: COLORS.tableHeaderText,
      fontStyle: 'bold',
      fontSize: 7.5,
      halign: 'center',
    },
    alternateRowStyles: {
      fillColor: COLORS.tableAlt,
    },
    margin: {
      left: PAGE.margin.left,
      right: PAGE.margin.right,
      top: PAGE.margin.top + HEADER_HEIGHT,
      bottom: PAGE.margin.bottom + FOOTER_HEIGHT,
    },
    tableLineColor: COLORS.tableBorder,
    tableLineWidth: 0.2,
  };
}

// ====================================================================
// Chart Capture
// ====================================================================
async function captureChartImage(element: HTMLElement): Promise<string | null> {
  try {
    const canvas = await html2canvas(element, {
      scale: 2.5,
      backgroundColor: '#ffffff',
      useCORS: true,
      allowTaint: true,
      logging: false,
    });
    return canvas.toDataURL('image/png');
  } catch (error) {
    console.error('Chart capture failed:', error);
    return null;
  }
}

async function addChartToPage(
  doc: jsPDF,
  chartElement: HTMLElement,
  title: string,
  startY?: number
): Promise<void> {
  const imgData = await captureChartImage(chartElement);
  if (!imgData) return;

  const y = startY ?? PAGE.margin.top + HEADER_HEIGHT + 5;

  // Section title
  const titleY = drawSectionTitle(doc, title, y);

  // Calculate image dimensions
  const maxWidth = CONTENT_WIDTH;
  const maxHeight = PAGE.height - titleY - PAGE.margin.bottom - FOOTER_HEIGHT - 5;

  const img = new Image();
  img.src = imgData;
  await new Promise<void>((resolve) => {
    img.onload = () => resolve();
    img.onerror = () => resolve();
  });

  const aspectRatio = img.width / img.height;
  let imgWidth = maxWidth;
  let imgHeight = imgWidth / aspectRatio;

  if (imgHeight > maxHeight) {
    imgHeight = maxHeight;
    imgWidth = imgHeight * aspectRatio;
  }

  const x = PAGE.margin.left + (CONTENT_WIDTH - imgWidth) / 2;

  // Light border around chart
  doc.setDrawColor(...COLORS.tableBorder);
  doc.setLineWidth(0.3);
  doc.roundedRect(x - 1, titleY - 1, imgWidth + 2, imgHeight + 2, 1, 1, 'S');

  doc.addImage(imgData, 'PNG', x, titleY, imgWidth, imgHeight);
}

// ====================================================================
// DOM Data Extraction
// ====================================================================
function extractTableDataFromDOM(container: HTMLElement): {
  headers: string[];
  rows: string[][];
} | null {
  const table = container.querySelector('table');
  if (!table) return null;

  const headers: string[] = [];
  const rows: string[][] = [];

  // Try to get headers from thead
  const thead = table.querySelector('thead');
  if (thead) {
    const ths = thead.querySelectorAll('th');
    ths.forEach((th) => headers.push(th.textContent?.trim() || ''));
  }

  // Get body rows
  const tbody = table.querySelector('tbody');
  if (tbody) {
    const trs = tbody.querySelectorAll('tr');
    trs.forEach((tr) => {
      const cells: string[] = [];
      tr.querySelectorAll('td, th').forEach((cell) => {
        cells.push(cell.textContent?.trim() || '');
      });
      if (cells.length > 0) rows.push(cells);
    });
  }

  if (headers.length === 0 && rows.length === 0) return null;
  return { headers, rows };
}

// For PostInsight transposed table: rows are metrics, columns are posts
function extractPostInsightDataFromDOM(container: HTMLElement): {
  headers: string[];
  rows: string[][];
  rowLinks: string[];
} | null {
  const table = container.querySelector('table');
  if (!table) return null;

  const tbody = table.querySelector('tbody');
  if (!tbody) return null;

  const trs = tbody.querySelectorAll('tr');
  if (trs.length === 0) return null;

  // Extract metric labels and values per post
  const metrics: { label: string; values: string[] }[] = [];
  let postLinks: string[] = [];
  trs.forEach((tr) => {
    const cells = tr.querySelectorAll('td, th');
    if (cells.length < 2) return;
    const label = cells[0].textContent?.trim() || '';

     if (label === '投稿日' && postLinks.length === 0) {
      postLinks = Array.from(cells)
        .slice(1)
        .map((cell) => {
          const anchor = cell.querySelector('a[href]');
          return anchor instanceof HTMLAnchorElement ? anchor.href : '';
        });
    }

    // Skip thumbnail row
    if (label === 'サムネイル') return;
    const values: string[] = [];
    for (let i = 1; i < cells.length; i++) {
      values.push(cells[i].textContent?.trim() || '');
    }
    metrics.push({ label, values });
  });

  if (metrics.length === 0) return null;

  // Transpose: convert from row=metric,col=post to row=post,col=metric
  const numPosts = metrics[0].values.length;
  const headers = ['No.', '投稿リンク', ...metrics.map((m) => m.label)];
  const rows: string[][] = [];
  const rowLinks: string[] = [];

  for (let i = 0; i < numPosts; i++) {
    const row = [String(i + 1), '開く'];
    metrics.forEach((m) => {
      row.push(m.values[i] || '');
    });
    rows.push(row);
    rowLinks.push(postLinks[i] || '');
  }

  return { headers, rows, rowLinks };
}

// ====================================================================
// Account Name Detection
// ====================================================================
function detectAccountInfo(): PdfAccountInfo {
  if (typeof window !== 'undefined') {
    try {
      const selectedInstagramUserId = localStorage.getItem(STORAGE_KEYS.SELECTED_ACCOUNT);
      const accountsCache = localStorage.getItem(STORAGE_KEYS.ACCOUNTS_CACHE);

      if (accountsCache) {
        const accounts = JSON.parse(accountsCache) as Array<{
          instagram_user_id?: string;
          username?: string;
          account_name?: string;
          is_active?: boolean;
        }>;

        const selectedAccount =
          accounts.find((account) => account.instagram_user_id === selectedInstagramUserId) ??
          accounts.find((account) => account.is_active) ??
          accounts[0];

        if (selectedAccount?.username) {
          const displayName = selectedAccount.account_name?.trim() || selectedAccount.username;
          const username = selectedAccount.username.replace(/^@/, '');
          const instagramUserId = selectedAccount.instagram_user_id?.trim();

          return {
            coverName: ensureHonorific(displayName),
            coverIdLine: instagramUserId
              ? `Instagram ID: @${username} / ${instagramUserId}`
              : `Instagram ID: @${username}`,
            fileNameBase: username,
          };
        }
      }
    } catch (error) {
      console.warn('Failed to detect account info for PDF cover:', error);
    }
  }

  const headerBtn = document.querySelector('header button span.font-medium');
  const usernameFromDom = headerBtn?.textContent?.trim().replace(/^@/, '');

  if (usernameFromDom) {
    return {
      coverName: ensureHonorific(usernameFromDom),
      coverIdLine: `Instagram ID: @${usernameFromDom}`,
      fileNameBase: usernameFromDom,
    };
  }

  return {
    coverName: 'Instagram Account 様',
    coverIdLine: 'Instagram ID: -',
    fileNameBase: 'instagram-account',
  };
}

// ====================================================================
// Report Builders
// ====================================================================

async function buildPostInsightReport(doc: jsPDF, container: HTMLElement): Promise<void> {
  const reportTitle = 'Instagram 投稿分析レポート';
  const accountInfo = detectAccountInfo();

  // Extract date range and post count from DOM
  const metaElements = container.closest('.space-y-6')?.querySelectorAll('.text-xs');
  let dateRange = '';
  let postInfo = '';
  metaElements?.forEach((el) => {
    const text = el.textContent || '';
    if (text.includes('件')) postInfo = text.trim();
    if (text.includes('最終更新')) dateRange = text.trim();
  });

  // Get date range from filter button
  const dateBtn = document.querySelector('#date');
  if (dateBtn?.textContent) {
    const match = dateBtn.textContent.match(/(\d{4}\/\d{2}\/\d{2})\s*-\s*(\d{4}\/\d{2}\/\d{2})/);
    if (match) dateRange = `${match[1]} ～ ${match[2]}`;
  }

  // Extract table data
  const tableData = extractPostInsightDataFromDOM(container);
  const numPosts = tableData?.rows.length ?? 0;

  // ---- Cover Page ----
  drawCoverPage(
    doc,
    '投稿分析 (Post Insight)',
    accountInfo.coverName,
    accountInfo.coverIdLine,
    postInfo || '投稿パフォーマンスの詳細レポート',
    {
    dateRange: dateRange || undefined,
    totalPosts: numPosts || undefined,
    }
  );

  // ---- Summary Page ----
  addPageWithHeader(doc, reportTitle);
  let y = PAGE.margin.top + HEADER_HEIGHT + 5;
  y = drawSectionTitle(doc, 'サマリー', y);

  // Compute summary from table data
  if (tableData && tableData.rows.length > 0) {
    const colIndex = (name: string) => tableData.headers.indexOf(name);
    const sum = (col: string) =>
      tableData.rows.reduce((s, r) => {
        const idx = colIndex(col);
        if (idx < 0) return s;
        const val = parseInt(r[idx].replace(/,/g, ''), 10);
        return s + (isNaN(val) ? 0 : val);
      }, 0);

    const avgEgRate = (() => {
      const idx = colIndex('EG率(%)');
      if (idx < 0) return 0;
      const rates = tableData.rows
        .map((r) => parseFloat(r[idx].replace('%', '')))
        .filter((v) => !isNaN(v));
      return rates.length > 0 ? rates.reduce((a, b) => a + b, 0) / rates.length : 0;
    })();

    const summaryCards = [
      { label: '総投稿数', value: `${numPosts}件`, sub: '対象期間内の投稿' },
      { label: '平均EG率', value: `${avgEgRate.toFixed(1)}%`, sub: 'エンゲージメント率の平均' },
      { label: '総リーチ数', value: formatNumber(sum('リーチ')), sub: 'リーチの合計' },
      { label: '総いいね数', value: formatNumber(sum('いいね')), sub: 'いいねの合計' },
      { label: '総コメント数', value: formatNumber(sum('コメント')), sub: 'コメントの合計' },
      { label: '総保存数', value: formatNumber(sum('保存')), sub: '保存の合計' },
    ];

    drawSummaryCards(doc, summaryCards, y);
  }

  // ---- Data Table ----
  if (tableData && tableData.rows.length > 0) {
    addPageWithHeader(doc, reportTitle);
    const tableStartY = PAGE.margin.top + HEADER_HEIGHT + 5;
    drawSectionTitle(doc, '投稿別パフォーマンス一覧', tableStartY);

    // Style numeric columns right-aligned
    const columnStyles: Record<number, Partial<{ halign: 'right' | 'left' | 'center' }>> = {};
    tableData.headers.forEach((h, i) => {
      if (i === 0) {
        columnStyles[i] = { halign: 'center' };
      } else if (h === '投稿リンク') {
        columnStyles[i] = { halign: 'center' };
      } else if (h === '投稿日' || h === 'タイプ') {
        columnStyles[i] = { halign: 'center' };
      } else {
        columnStyles[i] = { halign: 'right' };
      }
    });

    const linkColumnIndex = tableData.headers.indexOf('投稿リンク');

    autoTable(doc, {
      ...getAutoTableDefaults(),
      startY: tableStartY + 7,
      head: [tableData.headers],
      body: tableData.rows,
      columnStyles,
      didParseCell: (data) => {
        if (data.section === 'body' && data.column.index === linkColumnIndex) {
          data.cell.styles.textColor = [41, 98, 255];
          data.cell.styles.fontStyle = 'bold';
          data.cell.styles.halign = 'center';
        }
      },
      didDrawPage: (data) => {
        // Draw header on new pages created by autoTable
        if (data.pageNumber > 1) {
          drawPageHeader(doc, reportTitle);
        }
      },
      didDrawCell: (data) => {
        if (data.section !== 'body' || data.column.index !== linkColumnIndex) return;
        const url = tableData.rowLinks[data.row.index];
        if (!url) return;

        doc.link(data.cell.x, data.cell.y, data.cell.width, data.cell.height, { url });
      },
    });
  }

  // ---- Charts ----
  const chartCards = container.querySelectorAll('.recharts-responsive-container');
  for (let i = 0; i < chartCards.length; i++) {
    const chartParent = chartCards[i].closest('.w-full');
    if (chartParent) {
      addPageWithHeader(doc, reportTitle);
      await addChartToPage(
        doc,
        chartParent as HTMLElement,
        i === 0 ? 'エンゲージメント分析チャート' : `チャート ${i + 1}`,
      );
    }
  }
}

async function buildYearlyInsightReport(doc: jsPDF, container: HTMLElement): Promise<void> {
  const reportTitle = 'Instagram 年間分析レポート';
  const accountInfo = detectAccountInfo();

  // Get selected year
  const yearSelect = container.querySelector('[data-value]');
  const selectedYear = yearSelect?.textContent || new Date().getFullYear().toString();

  // ---- Cover Page ----
  drawCoverPage(
    doc,
    '年間分析 (Yearly Insight)',
    accountInfo.coverName,
    accountInfo.coverIdLine,
    `${selectedYear}年 月別パフォーマンス推移`,
    {
      dateRange: `${selectedYear}年1月 ～ ${selectedYear}年12月`,
    }
  );

  // ---- Data Table ----
  const tableData = extractTableDataFromDOM(container);
  if (tableData && tableData.rows.length > 0) {
    addPageWithHeader(doc, reportTitle);
    const tableStartY = PAGE.margin.top + HEADER_HEIGHT + 5;
    drawSectionTitle(doc, '月別データテーブル', tableStartY);

    const columnStyles: Record<number, Partial<{ halign: 'right' | 'left' | 'center' }>> = {};
    tableData.headers.forEach((_, i) => {
      columnStyles[i] = { halign: i === 0 ? 'center' : 'right' };
    });

    autoTable(doc, {
      ...getAutoTableDefaults(),
      startY: tableStartY + 7,
      head: [tableData.headers],
      body: tableData.rows,
      columnStyles,
      didDrawPage: (data) => {
        if (data.pageNumber > 1) {
          drawPageHeader(doc, reportTitle);
        }
      },
    });
  }

  // ---- Charts ----
  const chartCards = container.querySelectorAll('.recharts-responsive-container');
  for (let i = 0; i < chartCards.length; i++) {
    const chartParent = chartCards[i].closest('.w-full');
    if (chartParent) {
      addPageWithHeader(doc, reportTitle);
      await addChartToPage(
        doc,
        chartParent as HTMLElement,
        i === 0 ? 'エンゲージメント分析' : `チャート ${i + 1}`,
      );
    }
  }
}

async function buildMonthlyInsightReport(doc: jsPDF, container: HTMLElement): Promise<void> {
  const reportTitle = 'Instagram 月間分析レポート';
  const accountInfo = detectAccountInfo();

  // Get selected month
  const monthSelect = container.querySelector('button[role="combobox"]');
  const selectedMonth = monthSelect?.textContent || '';

  // ---- Cover Page ----
  drawCoverPage(
    doc,
    '月間分析 (Monthly Insight)',
    accountInfo.coverName,
    accountInfo.coverIdLine,
    `${selectedMonth} 日別パフォーマンス推移`,
    {
      dateRange: selectedMonth || undefined,
    }
  );

  // ---- Data Table ----
  const tableData = extractTableDataFromDOM(container);
  if (tableData && tableData.rows.length > 0) {
    addPageWithHeader(doc, reportTitle);
    const tableStartY = PAGE.margin.top + HEADER_HEIGHT + 5;
    drawSectionTitle(doc, '日別データテーブル', tableStartY);

    const columnStyles: Record<number, Partial<{ halign: 'right' | 'left' | 'center' }>> = {};
    tableData.headers.forEach((_, i) => {
      columnStyles[i] = { halign: i === 0 ? 'center' : 'right' };
    });

    autoTable(doc, {
      ...getAutoTableDefaults(),
      startY: tableStartY + 7,
      head: [tableData.headers],
      body: tableData.rows,
      columnStyles,
      didDrawPage: (data) => {
        if (data.pageNumber > 1) {
          drawPageHeader(doc, reportTitle);
        }
      },
    });
  }

  // ---- Charts ----
  const chartLabels = ['新規フォロワー推移', 'インプレッション・リーチ推移', 'プロフィール閲覧推移', 'ウェブサイトタップ推移'];
  const chartCards = container.querySelectorAll('.recharts-responsive-container');
  for (let i = 0; i < chartCards.length; i++) {
    const chartParent = chartCards[i].closest('.w-full');
    if (chartParent) {
      addPageWithHeader(doc, reportTitle);
      await addChartToPage(
        doc,
        chartParent as HTMLElement,
        chartLabels[i] || `チャート ${i + 1}`,
      );
    }
  }
}

// ====================================================================
// Main Export Function
// ====================================================================
export const exportToPDF = async (): Promise<boolean> => {
  try {
    console.log('PDF export started...');

    // Detect current page by element IDs
    const yearlyElement = document.getElementById('yearly-analysis-content');
    const monthlyElement = document.getElementById('monthly-analysis-content');
    const postElement = document.getElementById('post-analysis-content');

    let currentElement: HTMLElement | null = null;
    let pageType: 'yearly' | 'monthly' | 'post' = 'post';

    if (yearlyElement) {
      currentElement = yearlyElement;
      pageType = 'yearly';
    } else if (monthlyElement) {
      currentElement = monthlyElement;
      pageType = 'monthly';
    } else if (postElement) {
      currentElement = postElement;
      pageType = 'post';
    }

    if (!currentElement) {
      throw new Error('No analysis content found on current page');
    }

    // Create PDF
    const doc = new jsPDF('p', 'mm', 'a4');

    // Load Japanese fonts
    await ensureFonts(doc);

    // Build report based on page type
    switch (pageType) {
      case 'post':
        await buildPostInsightReport(doc, currentElement);
        break;
      case 'yearly':
        await buildYearlyInsightReport(doc, currentElement);
        break;
      case 'monthly':
        await buildMonthlyInsightReport(doc, currentElement);
        break;
    }

    // Add page footers to all pages (headers already drawn during build)
    const totalPages = doc.getNumberOfPages();

    for (let i = 2; i <= totalPages; i++) {
      // Page 1 is cover, skip header for it
      doc.setPage(i);
      drawPageFooter(doc, i - 1, totalPages - 1); // Exclude cover from page count
    }

    // Also draw footer on cover page (with special treatment)
    doc.setPage(1);
    // Cover page has its own footer design, skip standard footer

    // Save
    const currentDate = formatDate(new Date()).replace(/\//g, '-');
    const accountInfo = detectAccountInfo();
    const fileName = `instagram-${pageType}-report-${accountInfo.fileNameBase}-${currentDate}.pdf`;
    doc.save(fileName);

    console.log(`PDF export completed: ${fileName}`);
    return true;
  } catch (error) {
    console.error('PDF export failed:', error);
    alert('PDFエクスポートに失敗しました。再度お試しください。');
    return false;
  }
};
