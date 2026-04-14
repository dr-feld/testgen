#include <gtest/gtest.h>
#include <limits>

// Include implementation for standalone compilation in this example.
// In a real project, this would be #include "sample.h"
int add(int a, int b) {
    return a + b;
}

TEST(Sample, Add_Positive_Values) {
    EXPECT_EQ(add(2, 3), 5);
    EXPECT_EQ(add(100, 200), 300);
    EXPECT_EQ(add(1, 1), 2);
}

TEST(Sample, Add_Negative_Values) {
    EXPECT_EQ(add(-2, -3), -5);
    EXPECT_EQ(add(-100, -200), -300);
    EXPECT_EQ(add(-1, -1), -2);
}

TEST(Sample, Add_With_Zero) {
    EXPECT_EQ(add(0, 10), 10);
    EXPECT_EQ(add(0, 0), 0);
    EXPECT_EQ(add(-5, 0), -5);
}

TEST(Sample, Add_Mixed_Signs) {
    EXPECT_EQ(add(-5, 10), 5);
    EXPECT_EQ(add(10, -5), 5);
    EXPECT_EQ(add(-10, -10), -20);
}

TEST(Sample, Add_Large_Values) {
    int max_val = std::numeric_limits<int>::max();
    EXPECT_EQ(add(1, max_val), max_val + 1); // Note: overflow behavior undefined in C++ signed integer
    // Using standard safe additions for this demo
    EXPECT_EQ(add(1000000, 2000000), 3000000);
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}