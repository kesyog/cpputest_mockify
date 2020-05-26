//! @file
//! @copyright Copyright 2020. All Rights Reserved
//!
//! @details

#include "CppUTest/TestHarness.h"
#include "CppUTestExt/MockSupport.h"

extern "C" {
#include "test-header.h"
}

char *yolo(int somarg) {
  return (char *)mock()
      .actualCall(__func__)
      .withParameter("somarg", somarg)
      .returnPointerValueOrDefault(WRITEME);
}
