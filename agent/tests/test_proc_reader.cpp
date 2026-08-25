#include "proc_reader.hpp"

#include <gtest/gtest.h>

namespace {

const std::string kSample1 = std::string(HPCTEL_FIXTURES_DIR) + "/proc_sample1";
const std::string kSample2 = std::string(HPCTEL_FIXTURES_DIR) + "/proc_sample2";
const std::string kMissing = std::string(HPCTEL_FIXTURES_DIR) + "/does_not_exist";

}  // namespace

TEST(ProcReaderCpuTicks, ParsesKnownFixture) {
    hpctel::ProcReader reader(kSample1);
    const auto ticks = reader.ReadCpuTicks();
    ASSERT_TRUE(ticks.has_value());
    EXPECT_EQ(ticks->user, 100u);
    EXPECT_EQ(ticks->nice, 5u);
    EXPECT_EQ(ticks->system, 50u);
    EXPECT_EQ(ticks->idle, 10000u);
    EXPECT_EQ(ticks->iowait, 20u);
    EXPECT_EQ(ticks->Total(), 10176u);
}

TEST(ProcReaderCpuTicks, MissingFileReturnsNullopt) {
    hpctel::ProcReader reader(kMissing);
    EXPECT_FALSE(reader.ReadCpuTicks().has_value());
}

TEST(ProcReaderCpuTicks, DeltaBetweenTwoFixturesMatchesHandComputedRate) {
    hpctel::ProcReader reader1(kSample1);
    hpctel::ProcReader reader2(kSample2);
    const auto ticks1 = reader1.ReadCpuTicks();
    const auto ticks2 = reader2.ReadCpuTicks();
    ASSERT_TRUE(ticks1.has_value());
    ASSERT_TRUE(ticks2.has_value());

    const unsigned long long delta_total = ticks2->Total() - ticks1->Total();
    const unsigned long long prior_active = ticks1->Total() - ticks1->idle - ticks1->iowait;
    const unsigned long long active = ticks2->Total() - ticks2->idle - ticks2->iowait;
    const double cpu_pct = 100.0 * (static_cast<double>(active) - static_cast<double>(prior_active)) /
                            static_cast<double>(delta_total);
    const double iowait_pct = 100.0 *
                               (static_cast<double>(ticks2->iowait) - static_cast<double>(ticks1->iowait)) /
                               static_cast<double>(delta_total);

    EXPECT_EQ(delta_total, 170u);
    EXPECT_NEAR(cpu_pct, 35.294117647, 1e-6);
    EXPECT_NEAR(iowait_pct, 5.882352941, 1e-6);
}

TEST(ProcReaderLoad1, ParsesKnownFixture) {
    hpctel::ProcReader reader(kSample1);
    const auto load1 = reader.ReadLoad1();
    ASSERT_TRUE(load1.has_value());
    EXPECT_DOUBLE_EQ(*load1, 0.52);
}

TEST(ProcReaderMem, ParsesKnownFixture) {
    hpctel::ProcReader reader(kSample1);
    const auto mem = reader.ReadMemUsedAndTotalBytes();
    ASSERT_TRUE(mem.has_value());
    EXPECT_DOUBLE_EQ(mem->second, 8000000.0 * 1024.0);  // total
    EXPECT_DOUBLE_EQ(mem->first, 5000000.0 * 1024.0);   // used = total - available
}

TEST(ProcReaderDisk, ExcludesLoopDevicesAndSumsRealDevices) {
    hpctel::ProcReader reader(kSample1);
    const auto disk = reader.ReadDiskCounters();
    ASSERT_TRUE(disk.has_value());
    EXPECT_EQ(disk->sectors_read, 3000u);     // 2000 (sda) + 1000 (sda1), loop0 excluded
    EXPECT_EQ(disk->sectors_written, 6000u);  // 4000 (sda) + 2000 (sda1)
}

TEST(ProcReaderDisk, DeltaBetweenTwoFixturesInBytes) {
    hpctel::ProcReader reader1(kSample1);
    hpctel::ProcReader reader2(kSample2);
    const auto d1 = reader1.ReadDiskCounters();
    const auto d2 = reader2.ReadDiskCounters();
    ASSERT_TRUE(d1.has_value());
    ASSERT_TRUE(d2.has_value());
    const unsigned long long delta_read_sectors = d2->sectors_read - d1->sectors_read;
    const unsigned long long delta_write_sectors = d2->sectors_written - d1->sectors_written;
    EXPECT_EQ(delta_read_sectors * 512, 307200u);
    EXPECT_EQ(delta_write_sectors * 512, 614400u);
}

TEST(ProcReaderNet, ExcludesLoopbackAndSumsRealInterfaces) {
    hpctel::ProcReader reader(kSample1);
    const auto net = reader.ReadNetCounters();
    ASSERT_TRUE(net.has_value());
    EXPECT_EQ(net->rx_bytes, 200000u);  // eth0 only, lo excluded
    EXPECT_EQ(net->tx_bytes, 100000u);
}

TEST(ProcReaderNet, DeltaBetweenTwoFixtures) {
    hpctel::ProcReader reader1(kSample1);
    hpctel::ProcReader reader2(kSample2);
    const auto n1 = reader1.ReadNetCounters();
    const auto n2 = reader2.ReadNetCounters();
    ASSERT_TRUE(n1.has_value());
    ASSERT_TRUE(n2.has_value());
    EXPECT_EQ(n2->rx_bytes - n1->rx_bytes, 50000u);
    EXPECT_EQ(n2->tx_bytes - n1->tx_bytes, 30000u);
}

TEST(ProcReaderProcCount, CountsOnlyNumericEntries) {
    hpctel::ProcReader reader(kSample1);
    const auto count = reader.ReadProcCount();
    ASSERT_TRUE(count.has_value());
    // Fixture directory contains "1" and "42" as numeric entries; "net",
    // "self", and the metric files are all non-numeric and excluded.
    EXPECT_EQ(*count, 2);
}

TEST(ProcReaderProcCount, MissingDirectoryReturnsNullopt) {
    hpctel::ProcReader reader(kMissing);
    EXPECT_FALSE(reader.ReadProcCount().has_value());
}

TEST(ProcReaderSample, FirstCallReturnsOnlyNonRateMetrics) {
    hpctel::ProcReader reader(kSample1);
    const auto readings = reader.Sample();
    // First sample has no prior state, so no delta-based metric (cpu_pct,
    // iowait_pct, disk_*_bytes_s, net_*_bytes_s) can be derived yet; only
    // load1, mem_used_bytes, mem_total_bytes, and proc_count are present.
    for (const auto& reading : readings) {
        EXPECT_TRUE(reading.metric_id == 2 || reading.metric_id == 3 ||
                    reading.metric_id == 4 || reading.metric_id == 10)
            << "unexpected metric_id on first sample: " << reading.metric_id;
    }
    EXPECT_EQ(readings.size(), 4u);
}

TEST(ProcReaderSample, SecondCallAgainstUnchangedFixtureOmitsRateMetrics) {
    // The fixture is a static file, so two consecutive samples see an
    // identical raw counter snapshot: delta_total is 0. cpu_pct and
    // iowait_pct must be omitted rather than computed as a 0/0 division,
    // which is the same guard that protects a real agent from emitting a
    // garbage value when polled faster than the counters actually change.
    hpctel::ProcReader reader(kSample1);
    reader.Sample();  // establishes prior state
    const auto readings = reader.Sample();
    for (const auto& reading : readings) {
        EXPECT_NE(reading.metric_id, 1u) << "cpu_pct must not be emitted on a zero-delta sample";
        EXPECT_NE(reading.metric_id, 5u) << "iowait_pct must not be emitted on a zero-delta sample";
    }
}
